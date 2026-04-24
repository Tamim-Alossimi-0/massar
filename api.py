"""
api.py - FastAPI backend for the Saudi Resume-Job Matcher.

Exposes the matching engine as REST endpoints for a Next.js frontend:
  POST /api/match           - rank jobs against an uploaded CV
  POST /api/skills/extract  - extract known skills from free text
  GET  /api/jobs/stats      - market dashboard aggregates (cached)
  POST /api/gap-report      - CV gap report from match results
  POST /api/jobs/refresh    - re-run the collector pipeline

Run (dev):  uvicorn api:app --reload --port 8000
"""
from __future__ import annotations

import io
import logging
import sys
import tempfile
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import (
    FastAPI, File, Form, HTTPException, UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent))

from utils import SKILLS_VOCAB, extract_skills, parse_pdf
from model import (
    load_jobs, get_top_matches, filter_by_location,
    prime_embeddings,
)
from gap_report import (
    categorise_title, parse_salary, generate_gap_report,
)

logging.basicConfig(
    level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("api")

JOBS_PATH = Path(__file__).parent / "data" / "processed" / "jobs_clean.csv"


# -- App state (populated by lifespan) --

class _State:
    jobs_df: Optional[pd.DataFrame] = None
    # Cache of pre-computed stats keyed by CSV mtime
    stats_cache: Dict[float, Dict[str, Any]] = {}
    # Flag: embeddings have been encoded for the currently loaded jobs_df
    primed: bool = False


state = _State()


# -- Startup / shutdown --

@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Load the jobs DataFrame and prime embeddings at startup.

    With the embedding cache shipped in the Docker image, prime_embeddings()
    loads the pre-computed .npy + pickles off disk in under a second, so we
    pay that cost once during container boot and every /api/match request
    is fast from the first hit. If the cache is ever missing (e.g. local
    dev after a fresh clone), the first boot re-encodes the corpus — still
    better done here than blocking a user-facing request.
    """
    _load_jobs_only()
    _ensure_primed()
    log.info("Server ready.")
    yield
    log.info("API shutting down")


def _load_jobs_only() -> None:
    """Cheap startup path: read the CSV, attach cluster labels. No encoding."""
    if not JOBS_PATH.exists():
        log.warning("Job data not found at %s - endpoints will return 503", JOBS_PATH)
        state.jobs_df = None
        state.primed = False
        return
    log.info("Loading jobs from %s", JOBS_PATH)
    state.jobs_df = load_jobs(str(JOBS_PATH))
    state.stats_cache.clear()
    state.primed = False
    log.info("Loaded %d jobs (embeddings not yet primed)", len(state.jobs_df))


def _ensure_primed() -> None:
    """Idempotent: encodes the job corpus into the vector store on first call
    after load or refresh. Subsequent calls are no-ops."""
    if state.primed or state.jobs_df is None or state.jobs_df.empty:
        return
    log.info("Priming embeddings for %d jobs (first request - this may take a minute)...",
             len(state.jobs_df))
    prime_embeddings(state.jobs_df)
    state.primed = True
    log.info("Embeddings ready.")


# -- FastAPI app + CORS --

app = FastAPI(
    title="Saudi Resume-Job Matcher API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -- Helpers --

def _require_jobs() -> pd.DataFrame:
    if state.jobs_df is None or state.jobs_df.empty:
        raise HTTPException(
            status_code=503,
            detail="Job dataset not available. Run POST /api/jobs/refresh first.",
        )
    return state.jobs_df


def _parse_uploaded_cv(cv_file: UploadFile) -> str:
    suffix = Path(cv_file.filename or "cv").suffix.lower()
    content = cv_file.file.read()
    if suffix == ".pdf":
        with tempfile.NamedTemporaryFile(
            suffix=".pdf", delete=False, dir=str(Path("data"))
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            return parse_pdf(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    # Treat everything else as text
    return content.decode("utf-8", errors="ignore")


def _matches_to_payload(matches: pd.DataFrame) -> List[Dict[str, Any]]:
    """Convert matches DataFrame into a JSON-safe list of dicts."""
    if matches.empty:
        return []
    out: List[Dict[str, Any]] = []
    for _, row in matches.iterrows():
        out.append({
            "job_title":         row.get("job_title", ""),
            "company":           row.get("company", ""),
            "location":          row.get("location", ""),
            "salary_range":      row.get("salary_range", ""),
            "experience_years":  int(row.get("experience_years", 0) or 0),
            "overall_score":     float(row.get("overall_score", 0.0)),
            "semantic_score":    float(row.get("semantic_score", 0.0)),
            "skills_score":      float(row.get("skills_score", 0.0)),
            "experience_score":  float(row.get("experience_score", 0.0)),
            "match_explanation": row.get("match_explanation", ""),
            "matched_skills":    [s for s in str(row.get("matched_skills", "")).split(", ") if s],
            "missing_skills":    [s for s in str(row.get("missing_skills", "")).split(", ") if s],
            "skill_importance":  _safe_json(row.get("skill_importance", "{}")),
        })
    return out


def _safe_json(raw: Any) -> Dict[str, str]:
    import json
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


# -- Pydantic request / response models --

class SkillExtractResponse(BaseModel):
    skills:  List[str]
    cv_text: str = ""


class GapReportRequest(BaseModel):
    matches:            List[Dict[str, Any]] = Field(default_factory=list)
    cv_skills:          List[str] = Field(default_factory=list)
    experience_years:   int = 0
    cv_text:            str = ""


class RefreshResponse(BaseModel):
    success:       bool
    job_count:     int
    message:       str


# -- Endpoints --

@app.get("/", tags=["meta"])
async def root() -> Dict[str, Any]:
    return {
        "name":    "Saudi Resume-Job Matcher API",
        "version": "1.0.0",
        "jobs":    0 if state.jobs_df is None else len(state.jobs_df),
        "endpoints": [
            "POST /api/match",
            "POST /api/skills/extract",
            "GET  /api/jobs/stats",
            "POST /api/gap-report",
            "POST /api/jobs/refresh",
        ],
    }


@app.post("/api/match", tags=["matching"])
async def match_cv(
    experience_years: int = Form(0, ge=0, le=60),
    seniority_label:  str = Form("All"),
    keyword_search:   str = Form(""),
    top_n:            int = Form(10, ge=1, le=50),
    user_skills:      List[str] = Form(default_factory=list),
    cv_text:          Optional[str] = Form(None),
    cv_file:          Optional[UploadFile] = File(None),
) -> Dict[str, Any]:
    """
    Rank jobs against the provided CV. Accepts either a multipart file
    upload (PDF or TXT) under `cv_file` OR a plain `cv_text` form field.
    """
    jobs_df = _require_jobs()
    _ensure_primed()

    # Resolve CV text
    text: str = ""
    if cv_file is not None and cv_file.filename:
        try:
            text = _parse_uploaded_cv(cv_file)
        except Exception as exc:
            raise HTTPException(400, f"Failed to parse uploaded CV: {exc}") from exc
    elif cv_text and cv_text.strip():
        text = cv_text

    if not text.strip():
        raise HTTPException(400, "Provide either cv_file or cv_text.")

    # Apply pre-search filters (mirrors app.py logic)
    filtered = filter_by_location(jobs_df, "Riyadh")
    if keyword_search.strip():
        kw = keyword_search.strip().lower()
        filtered = filtered[
            filtered["job_title"].str.lower().str.contains(kw, na=False, regex=False) |
            filtered["company"].str.lower().str.contains(kw, na=False, regex=False)
        ]
    if filtered.empty:
        return {"matches": [], "total_candidates": 0,
                "filters_applied": {"keyword": keyword_search, "seniority": seniority_label}}

    eff_n = min(top_n, len(filtered))
    matches = get_top_matches(
        text,
        filtered,
        full_df=jobs_df,
        top_n=eff_n,
        user_experience_years=experience_years,
        user_skills=list(user_skills),
        location=None,
        seniority_label=seniority_label,
    )

    return {
        "matches":          _matches_to_payload(matches),
        "total_candidates": int(len(filtered)),
        "filters_applied":  {
            "keyword":   keyword_search,
            "seniority": seniority_label,
        },
    }


@app.post("/api/skills/extract", tags=["matching"],
          response_model=SkillExtractResponse)
async def extract_cv_skills(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
) -> SkillExtractResponse:
    """
    Extract known skills from an uploaded CV. Accepts either:
      - a multipart `file` (PDF or TXT) - server parses via parse_pdf/parse_text
      - a plain `text` field (for non-file previews)

    Returns both the extracted skills and the parsed CV text so the
    frontend can re-use the server-side parsing result (e.g. for the
    gap-report round trip) without shipping a PDF parser to the browser.
    """
    cv_text = ""
    if file is not None and file.filename:
        try:
            cv_text = _parse_uploaded_cv(file)
        except Exception as exc:
            log.exception("Skill extract: CV parse failed")
            raise HTTPException(400, f"Could not read uploaded file: {exc}") from exc
    elif text and text.strip():
        cv_text = text

    if not cv_text.strip():
        # Nothing to extract from - return empty rather than 400 so the UI
        # can show "no skills found" gracefully.
        return SkillExtractResponse(skills=[], cv_text="")

    skills = sorted(set(extract_skills(cv_text)))
    return SkillExtractResponse(skills=skills, cv_text=cv_text)


@app.get("/api/jobs/stats", tags=["analytics"])
async def jobs_stats() -> Dict[str, Any]:
    """
    Market dashboard aggregates. Cached by CSV mtime - cache invalidates
    automatically when /api/jobs/refresh rewrites the file.
    """
    jobs_df = _require_jobs()

    mtime = JOBS_PATH.stat().st_mtime
    if mtime in state.stats_cache:
        return state.stats_cache[mtime]

    stats = _compute_stats(jobs_df)
    state.stats_cache.clear()  # keep memory small - only hold the latest
    state.stats_cache[mtime] = stats
    return stats


def _compute_stats(jobs_df: pd.DataFrame) -> Dict[str, Any]:
    df = jobs_df.fillna("").copy()
    df["role_category"] = df["job_title"].apply(categorise_title)

    # Top skills (from required_skills across all jobs)
    counter: Counter[str] = Counter()
    for s in df["required_skills"]:
        if isinstance(s, str) and s.strip():
            counter.update(extract_skills(s))
    top_skills = [
        {"skill": k, "count": v}
        for k, v in counter.most_common(15)
    ]

    # Jobs by category
    jobs_by_category = [
        {"category": k, "count": int(v)}
        for k, v in df["role_category"].value_counts().items()
    ]

    # Salary by category (avg min / avg max)
    parsed = df["salary_range"].apply(parse_salary)
    df["_sal_min"] = parsed.apply(lambda t: t[0] if t else None)
    df["_sal_max"] = parsed.apply(lambda t: t[1] if t else None)
    sal_df = df.dropna(subset=["_sal_min", "_sal_max"])
    salary_by_category: List[Dict[str, Any]] = []
    if not sal_df.empty:
        grouped = sal_df.groupby("role_category").agg(
            avg_min=("_sal_min", "mean"),
            avg_max=("_sal_max", "mean"),
            sample_n=("_sal_min", "count"),
        ).reset_index()
        for _, row in grouped.iterrows():
            salary_by_category.append({
                "category": row["role_category"],
                "avg_min":  int(round(row["avg_min"])),
                "avg_max":  int(round(row["avg_max"])),
                "sample_n": int(row["sample_n"]),
            })

    # Experience distribution
    exp = pd.to_numeric(df.get("experience_years", 0), errors="coerce").fillna(0)
    buckets = {"0-2 yrs": 0, "2-5 yrs": 0, "5-8 yrs": 0, "8+ yrs": 0}
    for y in exp:
        if y < 2:
            buckets["0-2 yrs"] += 1
        elif y < 5:
            buckets["2-5 yrs"] += 1
        elif y < 8:
            buckets["5-8 yrs"] += 1
        else:
            buckets["8+ yrs"] += 1
    experience_distribution = [
        {"bucket": k, "count": int(v)} for k, v in buckets.items()
    ]

    # Top companies
    top_companies = [
        {"company": k, "count": int(v)}
        for k, v in df[df["company"].str.strip() != ""]["company"]
        .value_counts().head(15).items()
    ]

    return {
        "total_jobs":              int(len(df)),
        "unique_companies":        int(df["company"].nunique()),
        "top_skills":              top_skills,
        "jobs_by_category":        jobs_by_category,
        "salary_by_category":      salary_by_category,
        "experience_distribution": experience_distribution,
        "top_companies":           top_companies,
    }


@app.post("/api/gap-report", tags=["analytics"])
async def gap_report(req: GapReportRequest) -> Dict[str, Any]:
    """CV gap report from existing match results. Pure computation, no model calls."""
    if not req.matches:
        raise HTTPException(400, "matches list is empty - run /api/match first.")

    # Re-hydrate list-of-dicts into DataFrame with columns expected by generate_gap_report
    matches_df = pd.DataFrame(req.matches)
    if "matched_skills" in matches_df.columns:
        matches_df["matched_skills"] = matches_df["matched_skills"].apply(
            lambda v: ", ".join(v) if isinstance(v, list) else (v or "")
        )
    if "missing_skills" in matches_df.columns:
        matches_df["missing_skills"] = matches_df["missing_skills"].apply(
            lambda v: ", ".join(v) if isinstance(v, list) else (v or "")
        )
    if "skill_importance" in matches_df.columns:
        import json
        matches_df["skill_importance"] = matches_df["skill_importance"].apply(
            lambda v: json.dumps(v) if isinstance(v, dict) else (v or "{}")
        )

    report = generate_gap_report(
        matches_df=matches_df,
        cv_skills=req.cv_skills,
        user_experience_years=req.experience_years,
        cv_text=req.cv_text,
    )
    return report


@app.post("/api/jobs/refresh", tags=["data"], response_model=RefreshResponse)
async def refresh_jobs() -> RefreshResponse:
    """
    Trigger the collector pipeline (Jadarat -> LinkedIn -> Bayt -> synthetic fallback).
    Blocking call. Can take several minutes. On success, reloads the in-process job
    dataset and invalidates the stats cache.
    """
    try:
        from scraper import collect_jobs
    except ImportError as exc:
        raise HTTPException(500, f"Scraper unavailable: {exc}") from exc

    try:
        collect_jobs()
    except Exception as exc:
        log.exception("Refresh failed")
        raise HTTPException(500, f"Refresh failed: {exc}") from exc

    # Reload the DataFrame (cheap). Embeddings will be re-primed lazily on
    # the next /api/match request since state.primed is reset here.
    _load_jobs_only()
    count = 0 if state.jobs_df is None else len(state.jobs_df)
    return RefreshResponse(
        success=True,
        job_count=count,
        message=f"Pipeline completed. {count} jobs loaded.",
    )


# -----------------------------------------------------------------------------
# Entry point for `python api.py` (HF Spaces / local quick-start)
#
# uvicorn is still the normal production launcher (see Dockerfile CMD), but this
# block lets the app boot anywhere the runtime sets a PORT env var without
# needing a custom command. Default 7860 matches HF Spaces' Docker SDK port.
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 7860))
    uvicorn.run("api:app", host="0.0.0.0", port=port)
