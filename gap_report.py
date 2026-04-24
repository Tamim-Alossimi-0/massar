"""
gap_report.py - CV Gap Report analytics.

Given a ranked matches DataFrame and the user's CV skills / experience,
compute a self-contained report dict covering:
  - the user's best-fit role category
  - skills coverage (X of Y commonly required)
  - seniority label
  - top 5 missing skills and their frequency across matches
  - estimated overall-score boost if those skills were added
  - expected salary range from matched listings
  - experience gap vs. matched-role average
  - a plain-text version of the report ready for download

All helpers are pure functions; no Streamlit dependency.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

# -- Skill weight used for approximate boost estimation (must stay in sync
#    with W_SKILLS in model.py). If that constant moves, update here.
_W_SKILLS = 0.35


# -- Role categorisation (mirrors pages/1_Job_Market_Dashboard.py) --

_ROLE_RULES: List[Tuple[str, List[str]]] = [
    ("Data Science",           [r"data scientist", r"data science"]),
    ("ML / AI Engineering",    [r"machine learning", r"\bml\b", r"\bai\b",
                                r"ai engineer", r"deep learning", r"nlp"]),
    ("Data Analysis / BI",     [r"data analyst", r"business intelligence",
                                r"\bbi\b analyst", r"analytics"]),
    ("Data Engineering",       [r"data engineer", r"etl"]),
    ("DevOps / Cloud",         [r"devops", r"cloud", r"\bsre\b",
                                r"site reliability", r"platform engineer"]),
    ("Cybersecurity",          [r"security", r"cyber", r"infosec",
                                r"penetration"]),
    ("Software Engineering",   [r"software engineer", r"software developer",
                                r"backend", r"frontend", r"full[- ]?stack",
                                r"mobile", r"android", r"ios", r"web developer",
                                r"developer"]),
]


def categorise_title(title: str) -> str:
    if not isinstance(title, str):
        return "Other"
    t = title.lower()
    for label, patterns in _ROLE_RULES:
        for p in patterns:
            if re.search(p, t):
                return label
    return "Other"


# -- Seniority from years --

def _seniority_label(years: float) -> str:
    y = float(years) if years is not None else 0.0
    if y < 2:
        return "Entry"
    if y < 4:
        return "Junior"
    if y < 7:
        return "Mid"
    return "Senior"


# -- Salary parsing (reuses the dashboard format) --

_SALARY_RE = re.compile(r"([\d,]+)\s*[–\-~to]+\s*([\d,]+)", flags=re.IGNORECASE)


def parse_salary(s: Any) -> Optional[Tuple[int, int]]:
    if not isinstance(s, str) or not s.strip():
        return None
    m = _SALARY_RE.search(s)
    if not m:
        return None
    try:
        lo = int(m.group(1).replace(",", ""))
        hi = int(m.group(2).replace(",", ""))
    except ValueError:
        return None
    if lo <= 0 or hi <= 0 or hi < lo:
        return None
    return lo, hi


# -- Candidate name guess --

def _guess_candidate_name(cv_text: str) -> str:
    if not isinstance(cv_text, str):
        return "Candidate"
    for raw in cv_text.splitlines():
        line = raw.strip()
        if not line or len(line) > 60:
            continue
        letters = sum(ch.isalpha() for ch in line)
        if letters < 3:
            continue
        if any(kw in line.lower() for kw in (
            "curriculum", "resume", "cv", "@", "http", "phone", "email"
        )):
            continue
        words = line.split()
        if 1 < len(words) <= 5 and all(w[0].isalpha() for w in words if w):
            return line
    return "Candidate"


# -- Helpers to read the matches DataFrame's string-list columns --

def _parse_list(cell: Any) -> List[str]:
    if not isinstance(cell, str) or not cell.strip():
        return []
    return [s.strip() for s in cell.split(",") if s.strip()]


def _merge_skill_importance(matches_df: pd.DataFrame) -> Dict[str, str]:
    """
    Union skill_importance JSON across matches, promoting higher importance
    to 'high' whenever any match lists it required.
    Priority order: high > medium > low.
    """
    priority = {"high": 2, "medium": 1, "low": 0}
    merged: Dict[str, str] = {}
    for raw in matches_df.get("skill_importance", []):
        try:
            obj = json.loads(raw) if isinstance(raw, str) and raw.strip() else {}
        except Exception:
            obj = {}
        if not isinstance(obj, dict):
            continue
        for skill, imp in obj.items():
            if imp not in priority:
                continue
            if skill not in merged or priority[imp] > priority[merged[skill]]:
                merged[skill] = imp
    return merged


# -- Main entry point --

def generate_gap_report(
    matches_df: pd.DataFrame,
    cv_skills: Iterable[str],
    user_experience_years: int,
    cv_text: str,
    top_k: int = 10,
) -> Dict[str, Any]:
    """
    Compute the full gap report. Returns a dict with the keys documented
    in the module docstring plus `text_report` for download.

    Assumes matches_df columns: job_title, company, matched_skills (csv
    string), missing_skills (csv string), skill_importance (json string),
    salary_range, experience_years.
    """
    if matches_df is None or matches_df.empty:
        return {"error": "No matches to analyse."}

    top = matches_df.head(top_k).copy().reset_index(drop=True)
    cv_skills_set = {s.strip().lower() for s in cv_skills if str(s).strip()}

    # -- Role category: mode over top matches --
    top["_role"] = top["job_title"].apply(categorise_title)
    role_counts = top["_role"].value_counts()
    top_role = role_counts.index[0] if not role_counts.empty else "Other"

    # -- Skills coverage --
    required_counter: Counter[str] = Counter()
    for idx in range(len(top)):
        matched = _parse_list(top.iloc[idx].get("matched_skills", ""))
        missing = _parse_list(top.iloc[idx].get("missing_skills", ""))
        for s in set(matched) | set(missing):
            required_counter[s.lower()] += 1

    total_unique_skills = len(required_counter)
    cv_skills_covered = sum(1 for s in required_counter if s in cv_skills_set)

    # -- Seniority --
    seniority = _seniority_label(user_experience_years)

    # -- Top-5 missing skills (appear most often across matches, not in CV) --
    importance_map = _merge_skill_importance(top)
    missing_freq = [
        (skill, count, importance_map.get(skill, "medium"))
        for skill, count in required_counter.items()
        if skill not in cv_skills_set
    ]
    missing_freq.sort(key=lambda t: (-t[1], t[0]))
    top_missing = [
        {"skill": s, "jobs_requiring": c, "importance": imp}
        for s, c, imp in missing_freq[:5]
    ]

    # -- Estimated overall-score boost from adding those 5 skills --
    # Proxy: for each match, count how many of the 5 are in its missing_skills,
    # divide by that job's total skill denominator, average across matches,
    # scale by skill-signal weight. Coarse but honest.
    top5_set = {d["skill"] for d in top_missing}
    boost_contributions: List[float] = []
    for i in range(len(top)):
        matched = set(s.lower() for s in _parse_list(top.iloc[i].get("matched_skills", "")))
        missing = set(s.lower() for s in _parse_list(top.iloc[i].get("missing_skills", "")))
        denom = len(matched | missing)
        if denom == 0:
            continue
        gained_here = len(top5_set & missing)
        if gained_here == 0:
            continue
        boost_contributions.append(gained_here / denom)
    avg_skill_gain = (sum(boost_contributions) / len(top)) if len(top) else 0.0
    estimated_boost_pct = round(avg_skill_gain * _W_SKILLS * 100, 1)

    # -- Salary expectations --
    parsed = top["salary_range"].apply(parse_salary)
    lows = [p[0] for p in parsed if p]
    highs = [p[1] for p in parsed if p]
    if lows and highs:
        salary = {
            "avg_min":   int(round(sum(lows) / len(lows))),
            "avg_max":   int(round(sum(highs) / len(highs))),
            "sample_n":  len(lows),
        }
    else:
        salary = None

    # -- Experience gap --
    exp_years = pd.to_numeric(top.get("experience_years", 0), errors="coerce").fillna(0)
    non_zero = exp_years[exp_years > 0]
    experience_gap = None
    if not non_zero.empty:
        avg_required = float(non_zero.mean())
        if user_experience_years < avg_required - 1:
            experience_gap = {
                "avg_required":   round(avg_required, 1),
                "user_has":       int(user_experience_years),
                "suggested_tier": _seniority_label(max(0, user_experience_years)),
            }

    # -- Profile --
    candidate_name = _guess_candidate_name(cv_text)

    report: Dict[str, Any] = {
        "candidate_name":       candidate_name,
        "generated_on":         date.today().isoformat(),
        "top_role":             top_role,
        "role_distribution":    role_counts.to_dict(),
        "cv_skills_covered":    cv_skills_covered,
        "total_unique_skills":  total_unique_skills,
        "seniority":            seniority,
        "experience_years":     int(user_experience_years),
        "top_missing":          top_missing,
        "estimated_boost_pct":  estimated_boost_pct,
        "salary":               salary,
        "experience_gap":       experience_gap,
        "match_count":          len(top),
    }
    report["text_report"] = _format_text_report(report)
    return report


# -- Text report formatter --

def _format_text_report(r: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("CV GAP REPORT")
    lines.append("=" * 60)
    lines.append("Candidate:   {}".format(r["candidate_name"]))
    lines.append("Generated:   {}".format(r["generated_on"]))
    lines.append("Analysis of: top {} matching jobs in Riyadh".format(r["match_count"]))
    lines.append("")

    lines.append("PROFILE SUMMARY")
    lines.append("-" * 60)
    lines.append("Best-fit role category: {}".format(r["top_role"]))
    lines.append("Skill coverage:         {} of {} commonly required skills".format(
        r["cv_skills_covered"], r["total_unique_skills"]))
    lines.append("Experience level:       {} ({} years)".format(
        r["seniority"], r["experience_years"]))
    lines.append("")

    lines.append("SKILLS YOU SHOULD LEARN")
    lines.append("-" * 60)
    if r["top_missing"]:
        for item in r["top_missing"]:
            lines.append("  - {:<22} requested by {} of top matches  [{}]".format(
                item["skill"], item["jobs_requiring"], item["importance"]))
        lines.append("")
        lines.append("Adding these could raise your average match score by ~{}%.".format(
            r["estimated_boost_pct"]))
    else:
        lines.append("  Your CV covers all the commonly required skills. Nice.")
    lines.append("")

    if r["salary"]:
        s = r["salary"]
        lines.append("EXPECTED SALARY RANGE")
        lines.append("-" * 60)
        lines.append("{:,} - {:,} SAR / month".format(s["avg_min"], s["avg_max"]))
        lines.append("(from {} matched listings with structured salary data)".format(s["sample_n"]))
        lines.append("")

    if r["experience_gap"]:
        g = r["experience_gap"]
        lines.append("EXPERIENCE GAP")
        lines.append("-" * 60)
        lines.append("Most matching roles require ~{} years.".format(g["avg_required"]))
        lines.append("You have {} years.".format(g["user_has"]))
        lines.append("Consider targeting {} tier roles first.".format(g["suggested_tier"]))
        lines.append("")

    lines.append("-" * 60)
    lines.append("Generated by Saudi Resume-Job Matcher")
    return "\n".join(lines)
