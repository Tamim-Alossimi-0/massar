"""
model.py - Resume-Job Matching Engine

Architecture (4 scoring signals, weights sum to 1.0):
- Sentence Transformers (Nomic-embed-text-v1.5) for semantic similarity
- Direct skill overlap scoring with alias-aware extraction
- TF-IDF cosine similarity for lexical keyword matching
- Experience matching with sensible defaults

All state is in-memory (no ChromaDB, no persistent vector store).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

from utils import (
    extract_skills, extract_years_from_text,
    prepare_cv_for_embedding, prepare_job_for_embedding,
    SKILLS_VOCAB,
)

# -- Constants --
_MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"

# Disk cache — keyed on job row count so pre-built cache files can be
# shipped with the deployment and still be picked up on first run.
# Invalidates only when the row count changes (refresh pipeline produced
# a different-sized dataset) or when the cache files are absent.
CACHE_DIR             = Path("data/embeddings_cache")
EMBEDDINGS_PATH       = CACHE_DIR / "job_embeddings.npy"
META_PATH             = CACHE_DIR / "meta.json"
TFIDF_MATRIX_PATH     = CACHE_DIR / "tfidf_matrix.pkl"
TFIDF_VECTORIZER_PATH = CACHE_DIR / "tfidf_vectorizer.pkl"


def _read_cached_row_count() -> int:
    """Return row_count stored in meta.json, or -1 if unreadable."""
    if not META_PATH.exists():
        return -1
    try:
        return int(json.loads(META_PATH.read_text(encoding="utf-8"))
                   .get("row_count", -1))
    except Exception:
        return -1


def _write_cache_meta(row_count: int) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    META_PATH.write_text(
        json.dumps({"row_count": int(row_count)}),
        encoding="utf-8",
    )

# Scoring weights
W_SEMANTIC   = 0.40
W_SKILLS     = 0.35
W_TFIDF      = 0.15
W_EXPERIENCE = 0.10

SENIORITY_YEAR_RANGES: Dict[str, Tuple[int, int]] = {
    "All":               (0, 99),
    "Entry  (0-2 yrs)":  (0,  2),
    "Junior (2-5 yrs)":  (2,  5),
    "Mid    (5-8 yrs)":  (5,  8),
    "Senior (8+ yrs)":   (8, 99),
}

_SENIOR_TITLE_WORDS = re.compile(
    r"\b(?:senior|lead|staff|principal|manager|director|head|vp|chief)\b",
    re.IGNORECASE,
)
_ENTRY_JUNIOR_LABELS = {"Entry  (0-2 yrs)", "Junior (2-5 yrs)"}

# -- Singleton model --
_ST_MODEL: Optional[SentenceTransformer] = None


def _get_st_model() -> SentenceTransformer:
    global _ST_MODEL
    if _ST_MODEL is None:
        _ST_MODEL = SentenceTransformer(_MODEL_NAME, trust_remote_code=True)
    return _ST_MODEL


def embed_texts(texts: List[str], batch_size: int = 16) -> np.ndarray:
    """Encode texts into (n, 768) float32 matrix."""
    model = _get_st_model()
    print(f"  [Model] Encoding {len(texts)} texts in batches of {batch_size}...", flush=True)
    result = model.encode(
        texts, batch_size=batch_size,
        show_progress_bar=True, convert_to_numpy=True,
    )
    print(f"  [Model] Encoding complete.", flush=True)
    return result


# -- Job embedding cache (in-memory) --
_JOB_EMBEDDINGS: Optional[np.ndarray] = None
_JOB_EMBEDDINGS_COUNT: int = 0


def _get_job_embeddings(
    jobs_df: pd.DataFrame,
    csv_path: Optional[str] = None,  # kept for signature compat; unused
) -> np.ndarray:
    """
    Return the (n, 768) job embedding matrix. Cache hierarchy:
      1. In-memory singleton (same row count as before).
      2. On-disk cache at data/embeddings_cache/job_embeddings.npy, valid
         when meta.json reports the same row_count as jobs_df.
      3. Fresh encode with the Sentence-Transformer, then persist for
         next startup.
    """
    global _JOB_EMBEDDINGS, _JOB_EMBEDDINGS_COUNT
    n = len(jobs_df)

    if _JOB_EMBEDDINGS is not None and _JOB_EMBEDDINGS_COUNT == n:
        return _JOB_EMBEDDINGS

    # Disk cache — row-count-only check so shipped cache files load on
    # a fresh deployment without a matching CSV mtime.
    if EMBEDDINGS_PATH.exists() and _read_cached_row_count() == n:
        try:
            arr = np.load(EMBEDDINGS_PATH)
            if len(arr) == n:
                print(f"  [Model] Loaded {len(arr)} cached embeddings from disk.", flush=True)
                _JOB_EMBEDDINGS = arr
                _JOB_EMBEDDINGS_COUNT = n
                return _JOB_EMBEDDINGS
            print(f"  [Model] Cached embeddings size mismatch ({len(arr)} vs {n}); recomputing.", flush=True)
        except Exception as exc:
            print(f"  [Model] Embedding cache load failed ({exc}); recomputing.", flush=True)

    # Cache miss → encode from scratch
    print(f"  [Model] Encoding {n} jobs...", flush=True)
    texts = [prepare_job_for_embedding(row) for _, row in jobs_df.iterrows()]
    _JOB_EMBEDDINGS = embed_texts(texts)
    _JOB_EMBEDDINGS_COUNT = n
    print("  [Model] Done encoding jobs.", flush=True)

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        np.save(EMBEDDINGS_PATH, _JOB_EMBEDDINGS)
        _write_cache_meta(n)
        print(f"  [Model] Saved embeddings cache -> {EMBEDDINGS_PATH}", flush=True)
    except Exception as exc:
        print(f"  [Model] Embedding cache save failed: {exc}", flush=True)

    return _JOB_EMBEDDINGS


def prime_embeddings(full_df: pd.DataFrame, csv_path: Optional[str] = None) -> None:
    """Pre-compute (or load cached) job embeddings + TF-IDF on startup."""
    _get_job_embeddings(full_df, csv_path=csv_path)
    _get_tfidf(full_df, csv_path=csv_path)


# -- TF-IDF cache (in-memory singleton) --
# Fit once on the full corpus; transform CV and any filtered subset against
# the same vocabulary. Fitting per-call would recompute IDF on every filter
# change and defeat the purpose of caching.
_TFIDF_VECTORIZER: Optional[TfidfVectorizer] = None
_TFIDF_MATRIX = None  # scipy.sparse.csr_matrix over full corpus
_TFIDF_COUNT: int = 0


def _job_text_for_tfidf(row) -> str:
    """Plain text for TF-IDF (no Nomic task prefix — that's embedding-only)."""
    title = str(row.get("job_title", "")).strip()
    desc = str(row.get("description", "")).strip()
    skills = str(row.get("required_skills", "")).strip()
    return " ".join([p for p in (title, desc, skills) if p])


def _get_tfidf(full_df: pd.DataFrame, csv_path: Optional[str] = None):
    """
    Return (vectorizer, matrix). Cache hierarchy mirrors the embedding
    cache: in-memory → disk (tfidf_vectorizer.pkl + tfidf_matrix.pkl,
    keyed on meta.json row_count) → fresh fit.
    """
    global _TFIDF_VECTORIZER, _TFIDF_MATRIX, _TFIDF_COUNT
    n = len(full_df)

    if _TFIDF_VECTORIZER is not None and _TFIDF_COUNT == n:
        return _TFIDF_VECTORIZER, _TFIDF_MATRIX

    # Disk cache — both pickle files must exist and row_count must match.
    if (TFIDF_VECTORIZER_PATH.exists() and TFIDF_MATRIX_PATH.exists()
            and _read_cached_row_count() == n):
        try:
            vec = joblib.load(TFIDF_VECTORIZER_PATH)
            mat = joblib.load(TFIDF_MATRIX_PATH)
            if mat.shape[0] == n:
                print(f"  [Model] Loaded cached TF-IDF from disk ({mat.shape[0]} rows).", flush=True)
                _TFIDF_VECTORIZER = vec
                _TFIDF_MATRIX = mat
                _TFIDF_COUNT = n
                return _TFIDF_VECTORIZER, _TFIDF_MATRIX
            print(f"  [Model] Cached TF-IDF size mismatch ({mat.shape[0]} vs {n}); recomputing.", flush=True)
        except Exception as exc:
            print(f"  [Model] TF-IDF cache load failed ({exc}); recomputing.", flush=True)

    # Cache miss → fit from scratch
    print(f"  [Model] Fitting TF-IDF over {n} jobs...", flush=True)
    texts = [_job_text_for_tfidf(row) for _, row in full_df.iterrows()]
    _TFIDF_VECTORIZER = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95,
    )
    _TFIDF_MATRIX = _TFIDF_VECTORIZER.fit_transform(texts)
    _TFIDF_COUNT = n

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(_TFIDF_VECTORIZER, TFIDF_VECTORIZER_PATH)
        joblib.dump(_TFIDF_MATRIX,     TFIDF_MATRIX_PATH)
        _write_cache_meta(n)
        print(f"  [Model] Saved TF-IDF cache -> {TFIDF_VECTORIZER_PATH.name} + {TFIDF_MATRIX_PATH.name}", flush=True)
    except Exception as exc:
        print(f"  [Model] TF-IDF cache save failed: {exc}", flush=True)

    return _TFIDF_VECTORIZER, _TFIDF_MATRIX


# -- Filters --

def filter_by_location(jobs_df: pd.DataFrame, location: str = "") -> pd.DataFrame:
    if not location:
        return jobs_df
    return jobs_df[
        jobs_df["location"].str.contains(location, case=False, na=False)
    ]


def filter_by_experience(
    jobs_df: pd.DataFrame,
    seniority_label: str = "All",
) -> pd.DataFrame:
    if seniority_label == "All":
        return jobs_df

    lo, hi = SENIORITY_YEAR_RANGES.get(seniority_label, (0, 99))

    exp_col = jobs_df.get("experience_years", pd.Series(0, index=jobs_df.index))
    exp_num = pd.to_numeric(exp_col, errors="coerce").fillna(0).astype(int)
    desc_years = jobs_df["description"].fillna("").apply(extract_years_from_text)
    job_years = np.maximum(exp_num.values, desc_years.values)

    mask = (job_years >= lo) & (job_years <= hi)

    if seniority_label in _ENTRY_JUNIOR_LABELS:
        title_col = jobs_df["job_title"].fillna("").astype(str)
        senior_mask = title_col.str.contains(_SENIOR_TITLE_WORDS, regex=True, na=False)
        mask = mask & ~senior_mask

    return jobs_df[mask]


# -- Scoring functions --

def _compute_skill_score(
    cv_skills: set,
    job_required_skills: set,
    job_desc_skills: set,
) -> Tuple[float, set, set, Dict[str, str]]:
    all_job_skills = job_required_skills | job_desc_skills
    if not all_job_skills:
        return 0.5, set(), set(), {}

    matched = cv_skills & all_job_skills
    missing_pool = job_required_skills if job_required_skills else job_desc_skills
    missing = missing_pool - cv_skills

    total_weight = 0.0
    matched_weight = 0.0
    for s in all_job_skills:
        w = 2.0 if s in job_required_skills else 1.0
        total_weight += w
        if s in cv_skills:
            matched_weight += w

    score = matched_weight / total_weight if total_weight > 0 else 0.0

    # Low-signal penalty: jobs with <3 listed skills are too generic to
    # earn a high skill score (matching 1/1 shouldn't beat 8/12 on a
    # real technical role). Cap at 0.4 so semantic/TF-IDF decide these.
    if len(all_job_skills) < 3:
        score = min(score, 0.4)

    importance: Dict[str, str] = {}
    for s in sorted(matched | missing):
        if s in job_required_skills:
            importance[s] = "high"
        elif s in job_desc_skills:
            importance[s] = "medium"
        else:
            importance[s] = "low"

    return score, matched, missing, importance


def _compute_experience_score(
    cv_years: int,
    job_years: int,
    manual_input: bool = False,
) -> float:
    if job_years == 0:
        return 1.0 if manual_input else 0.8
    if not manual_input and cv_years == 0:
        return 0.5
    return min(cv_years / max(job_years, 1), 1.0)


def _build_explanation(
    overall_score: float,
    skill_score: float,
    exp_score: float,
    matched_skills: set,
    missing_skills: set,
    importance: Dict[str, str],
    cv_years: int,
    job_years: int,
) -> str:
    if overall_score >= 0.65:
        quality = "Strong match"
    elif overall_score >= 0.40:
        quality = "Good match"
    else:
        quality = "Partial match"

    parts = []

    if job_years > 0:
        if cv_years >= job_years:
            parts.append("you meet the experience requirement")
        else:
            gap = job_years - cv_years
            parts.append("you need {} more year(s) of experience".format(gap))

    req_matched = [s for s in matched_skills if importance.get(s) == "high"]
    if req_matched:
        top = req_matched[0].title()
        parts.append("you have the '{}' skill required for this role".format(top))
    elif matched_skills:
        top = sorted(matched_skills)[0].title()
        parts.append("your skill '{}' is relevant to this role".format(top))
    elif missing_skills:
        parts.append("consider adding more relevant skills to your CV")

    if not parts:
        return quality + "."

    body = " and ".join(parts)
    body = body[0].upper() + body[1:]
    return "{}. {}.".format(quality, body)


# -- Main matching API --

def load_jobs(filepath: str) -> pd.DataFrame:
    try:
        return pd.read_csv(filepath).fillna("")
    except Exception as exc:
        raise FileNotFoundError("Could not load jobs from '{}': {}".format(filepath, exc)) from exc


def get_top_matches(
    cv_text: str,
    jobs_df: pd.DataFrame,
    full_df: pd.DataFrame,
    top_n: int = 10,
    user_experience_years: Optional[int] = None,
    user_skills: Optional[List[str]] = None,
    location: Optional[str] = None,
    seniority_label: str = "All",
) -> pd.DataFrame:
    """
    Match a CV against jobs. Returns top N matches.

    Pipeline:
        1. Semantic similarity via Sentence Transformers (40%)
        2. Skill overlap with weighted required/description scoring (35%)
        3. TF-IDF cosine similarity — lexical keyword overlap (15%)
        4. Experience match (10%)
    """
    if jobs_df.empty:
        return pd.DataFrame()

    if location:
        jobs_df = filter_by_location(jobs_df, location)
    if seniority_label != "All":
        jobs_df = filter_by_experience(jobs_df, seniority_label=seniority_label)
    if jobs_df.empty:
        return pd.DataFrame()

    orig_indices = jobs_df.index.to_numpy()
    work = jobs_df.reset_index(drop=True)
    n = len(work)

    # Step 1: Semantic scores
    cv_embedding = embed_texts([prepare_cv_for_embedding(cv_text)])[0]
    all_embeddings = _get_job_embeddings(full_df)
    try:
        job_embeddings = all_embeddings[orig_indices]
    except IndexError:
        texts = [prepare_job_for_embedding(row) for _, row in work.iterrows()]
        job_embeddings = embed_texts(texts)

    semantic_scores = cosine_similarity(
        cv_embedding.reshape(1, -1), job_embeddings
    )[0]

    # Step 1b: TF-IDF lexical similarity (cached singleton fit on full corpus)
    tfidf_vec, tfidf_matrix_full = _get_tfidf(full_df)
    cv_tfidf = tfidf_vec.transform([cv_text])
    try:
        job_tfidf_subset = tfidf_matrix_full[orig_indices]
    except IndexError:
        # Fallback: jobs_df indices aren't positional into full_df.
        job_texts = [_job_text_for_tfidf(row) for _, row in work.iterrows()]
        job_tfidf_subset = tfidf_vec.transform(job_texts)
    tfidf_scores = cosine_similarity(cv_tfidf, job_tfidf_subset)[0].astype(np.float32)

    # Step 2: Skill scores
    cv_skills = set(user_skills) if user_skills else set(extract_skills(cv_text))

    skill_scores = np.zeros(n, dtype=np.float32)
    matched_skills_per_job = []
    missing_skills_per_job = []
    importance_per_job = []

    for i in range(n):
        job = work.iloc[i]
        job_req = set(extract_skills(str(job.get("required_skills", ""))))
        job_desc = set(extract_skills(str(job.get("description", ""))))
        score, matched, missing, importance = _compute_skill_score(cv_skills, job_req, job_desc)
        skill_scores[i] = score
        matched_skills_per_job.append(matched)
        missing_skills_per_job.append(missing)
        importance_per_job.append(importance)

    # Step 3: Experience scores
    manual_input = user_experience_years is not None
    cv_years = int(user_experience_years) if manual_input else extract_years_from_text(cv_text)

    exp_col = work.get("experience_years", pd.Series(0, index=work.index))
    exp_num = pd.to_numeric(exp_col, errors="coerce").fillna(0).astype(int)
    desc_years = work["description"].fillna("").apply(extract_years_from_text)
    job_years_arr = np.maximum(exp_num.values, desc_years.values).astype(int)

    exp_scores = np.array([
        _compute_experience_score(cv_years, int(jy), manual_input)
        for jy in job_years_arr
    ], dtype=np.float32)

    # Combine scores
    overall = (
        W_SEMANTIC   * semantic_scores
        + W_SKILLS     * skill_scores
        + W_TFIDF      * tfidf_scores
        + W_EXPERIENCE * exp_scores
    )

    # Select top N
    k = min(top_n, n)
    top_indices = np.argsort(-overall)[:k]

    # Build result rows
    rows: List[Dict] = []
    for i in top_indices:
        job = work.iloc[i]
        matched = matched_skills_per_job[i]
        missing = missing_skills_per_job[i]
        importance = importance_per_job[i]
        ov = float(overall[i])

        explanation = _build_explanation(
            overall_score=ov,
            skill_score=float(skill_scores[i]),
            exp_score=float(exp_scores[i]),
            matched_skills=matched,
            missing_skills=missing,
            importance=importance,
            cv_years=cv_years,
            job_years=int(job_years_arr[i]),
        )

        rows.append({
            "job_title":        str(job.get("job_title", "")),
            "company":          str(job.get("company", "")),
            "location":         str(job.get("location", "")),
            "overall_score":    round(ov, 4),
            "semantic_score":   round(float(semantic_scores[i]), 4),
            "skills_score":     round(float(skill_scores[i]), 4),
            "experience_score": round(float(exp_scores[i]), 4),
            "matched_skills":   ", ".join(sorted(matched)),
            "missing_skills":   ", ".join(sorted(missing)),
            "salary_range":     str(job.get("salary_range", job.get("salary", ""))),
            "experience_years": str(job.get("experience_years", "")),
            "match_explanation": explanation,
            "skill_importance": json.dumps(importance),
        })

    return pd.DataFrame(rows)


def score_breakdown(
    cv_text: str,
    job_text: str,
    job_required_skills: str = "",
    user_years: Optional[int] = None,
) -> Dict:
    """Single-pair scoring for evaluation/testing."""
    cv_emb = embed_texts([prepare_cv_for_embedding(cv_text)])
    job_emb = embed_texts([job_text])
    semantic = float(cosine_similarity(cv_emb, job_emb)[0, 0])

    cv_skills = set(extract_skills(cv_text))
    job_skills = set(extract_skills(job_text))
    req_skills = set(extract_skills(job_required_skills)) if job_required_skills else set()

    score, matched, missing, importance = _compute_skill_score(cv_skills, req_skills, job_skills)

    job_yrs = extract_years_from_text(job_text)
    manual = user_years is not None
    cv_yrs = int(user_years) if manual else extract_years_from_text(cv_text)
    exp_sc = _compute_experience_score(cv_yrs, job_yrs, manual)

    return {
        "semantic_score":   round(semantic, 4),
        "skills_score":     round(score, 4),
        "experience_score": round(exp_sc, 4),
        "matched_skills":   sorted(matched),
        "missing_skills":   sorted(missing),
        "skill_importance": importance,
    }
