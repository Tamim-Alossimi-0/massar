"""
linkedin_collector.py — LinkedIn jobs collector using python-jobspy.

Runs a set of keyword searches against LinkedIn for Riyadh, normalises the
output into our schema (job_title, company, location, description,
required_skills, experience_years, education, salary_range), writes the
raw pull to data/raw/linkedin_jobs.csv, and merges into
data/processed/jobs_clean.csv (dedup on title+company).

CLI: python linkedin_collector.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import List

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from utils import extract_skills, extract_years_from_text

try:
    from jobspy import scrape_jobs
except ImportError:
    scrape_jobs = None  # type: ignore[assignment]

logging.basicConfig(
    level=logging.INFO, format="%(levelname)s | %(message)s", stream=sys.stdout
)
log = logging.getLogger("linkedin_collector")

# Keyword list — tech roles common in Riyadh
KEYWORDS: List[str] = [
    "data scientist",
    "data analyst",
    "machine learning",
    "software engineer",
    "data engineer",
    "AI engineer",
    "python developer",
    "business intelligence",
    "frontend developer",
    "backend developer",
    "full stack developer",
    "devops engineer",
    "cloud engineer",
    "cybersecurity analyst",
    "product manager",
    "UX designer",
    "QA engineer",
    "mobile developer",
    "database administrator",
    "system administrator",
]
LOCATION = "Riyadh, Saudi Arabia"
RESULTS_PER_KEYWORD = 100

RAW_PATH = Path("data/raw/linkedin_jobs.csv")
PROCESSED_PATH = Path("data/processed/jobs_clean.csv")

SCHEMA_COLS = [
    "job_title", "company", "location", "description",
    "required_skills", "experience_years", "education", "salary_range",
]


def _format_salary(row: pd.Series) -> str:
    mn, mx, curr, interval = (
        row.get("min_amount"), row.get("max_amount"),
        row.get("currency"), row.get("interval"),
    )
    if pd.isna(mn) and pd.isna(mx):
        return ""
    curr = "" if pd.isna(curr) else str(curr)
    interval = "" if pd.isna(interval) else " / " + str(interval)
    if pd.notna(mn) and pd.notna(mx):
        return f"{int(mn):,} - {int(mx):,} {curr}{interval}".strip()
    amt = int(mn) if pd.notna(mn) else int(mx)
    return f"{amt:,} {curr}{interval}".strip()


def _normalise(raw: pd.DataFrame) -> pd.DataFrame:
    """Map jobspy DataFrame into our canonical schema."""
    if raw.empty:
        return pd.DataFrame(columns=SCHEMA_COLS)

    # Drop rows with no description — nothing to match against
    raw = raw.copy()
    raw["description"] = raw.get("description", "").fillna("").astype(str)
    raw = raw[raw["description"].str.strip().str.len() > 20]

    out = pd.DataFrame({
        "job_title":   raw.get("title", "").fillna("").astype(str).str.strip(),
        "company":     raw.get("company", "").fillna("").astype(str).str.strip(),
        "location":    raw.get("location", "").fillna("").astype(str).str.strip(),
        "description": raw["description"].str.strip(),
    })

    # Derived fields from description
    out["required_skills"]  = out["description"].apply(
        lambda t: ", ".join(extract_skills(t))
    )
    out["experience_years"] = out["description"].apply(extract_years_from_text)
    out["education"]        = ""
    out["salary_range"]     = raw.apply(_format_salary, axis=1)

    # Riyadh-only filter (location string is freeform from LinkedIn)
    out = out[out["location"].str.contains("Riyadh", case=False, na=False)]

    # Drop rows without a title or company
    out = out[(out["job_title"].str.len() > 0) & (out["company"].str.len() > 0)]
    return out[SCHEMA_COLS].reset_index(drop=True)


def collect_from_linkedin() -> pd.DataFrame:
    """
    Run the full keyword sweep against LinkedIn. Returns a normalised
    DataFrame in our schema. Empty DataFrame if jobspy unavailable or
    no results at all.
    """
    if scrape_jobs is None:
        log.error("python-jobspy not installed. Run: pip install python-jobspy")
        return pd.DataFrame(columns=SCHEMA_COLS)

    frames: List[pd.DataFrame] = []
    for kw in KEYWORDS:
        log.info("Searching LinkedIn: '%s' in %s", kw, LOCATION)
        try:
            df = scrape_jobs(
                site_name="linkedin",
                search_term=kw,
                location=LOCATION,
                results_wanted=RESULTS_PER_KEYWORD,
                linkedin_fetch_description=True,
                verbose=0,
            )
        except Exception as exc:
            log.warning("  '%s' failed: %s", kw, exc)
            continue
        if df is None or df.empty:
            log.info("  '%s' returned 0 results", kw)
            continue
        log.info("  '%s' -> %d raw hits", kw, len(df))
        frames.append(df)

    if not frames:
        return pd.DataFrame(columns=SCHEMA_COLS)

    raw_all = pd.concat(frames, ignore_index=True)

    # Persist raw pull (pre-normalisation) for debugging
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw_all.to_csv(RAW_PATH, index=False)
    log.info("Raw pull saved: %s (%d rows)", RAW_PATH, len(raw_all))

    normalised = _normalise(raw_all)
    log.info("After normalisation + Riyadh filter: %d jobs", len(normalised))
    return normalised


def merge_into_processed(new_jobs: pd.DataFrame) -> pd.DataFrame:
    """
    Merge new_jobs into data/processed/jobs_clean.csv, deduping on
    (job_title, company). Real (LinkedIn) rows take priority over any
    existing synthetic duplicate via keep='first' after putting new
    rows on top. Returns the resulting merged DataFrame.
    """
    if new_jobs.empty:
        log.warning("No new jobs to merge.")
        if PROCESSED_PATH.exists():
            return pd.read_csv(PROCESSED_PATH).fillna("")
        return pd.DataFrame(columns=SCHEMA_COLS)

    if PROCESSED_PATH.exists():
        existing = pd.read_csv(PROCESSED_PATH).fillna("")
        # Align columns to SCHEMA_COLS (add missing, drop extras)
        for c in SCHEMA_COLS:
            if c not in existing.columns:
                existing[c] = ""
        existing = existing[SCHEMA_COLS]
    else:
        existing = pd.DataFrame(columns=SCHEMA_COLS)

    # New rows first so dedup keeps the real LinkedIn row over synthetic
    merged = pd.concat([new_jobs, existing], ignore_index=True)
    merged["_key_t"] = merged["job_title"].str.lower().str.strip()
    merged["_key_c"] = merged["company"].str.lower().str.strip()
    merged = merged.drop_duplicates(subset=["_key_t", "_key_c"], keep="first")
    merged = merged.drop(columns=["_key_t", "_key_c"]).reset_index(drop=True)

    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(PROCESSED_PATH, index=False)
    log.info(
        "Merged: %d new + %d existing -> %d total (saved to %s)",
        len(new_jobs), len(existing), len(merged), PROCESSED_PATH,
    )
    return merged


def run_linkedin_collector() -> List[dict]:
    """
    Convenience entry point for scraper.py orchestration.
    Returns the normalised rows as a list of dicts (matches the
    run_jadarat_collector() contract).
    """
    new_jobs = collect_from_linkedin()
    if new_jobs.empty:
        return []
    merge_into_processed(new_jobs)
    return new_jobs.to_dict(orient="records")


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    jobs = run_linkedin_collector()
    print(f"\nCollected {len(jobs)} unique LinkedIn jobs in Riyadh "
          f"(from {len(KEYWORDS)} keywords x {RESULTS_PER_KEYWORD} results).")
    if PROCESSED_PATH.exists():
        merged = pd.read_csv(PROCESSED_PATH)
        print(f"Total unique jobs in {PROCESSED_PATH}: {len(merged)}")
