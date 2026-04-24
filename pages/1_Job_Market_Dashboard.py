"""
pages/1_Job_Market_Dashboard.py - Riyadh tech job market analytics.

Loads data/processed/jobs_clean.csv and renders aggregate views:
in-demand skills, role distribution, salaries, experience, top hirers.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# pages/ is one level below project root; make utils importable.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from utils import extract_skills  # noqa: E402


JOBS_PATH = _ROOT / "data" / "processed" / "jobs_clean.csv"

st.set_page_config(page_title="Riyadh Tech Job Market", layout="wide")


# -- Skill category colouring --

_LANGUAGES = {
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
    "ruby", "php", "swift", "kotlin", "scala", "r", "bash", "sql", "html",
    "css", "dart", "perl",
}
_ML_AI = {
    "machine learning", "deep learning", "nlp", "computer vision", "ai",
    "data science", "pytorch", "tensorflow", "keras", "scikit-learn",
    "hugging face", "llm", "transformers", "reinforcement learning",
    "statistics", "mathematics",
}


def _skill_category(skill: str) -> str:
    s = skill.lower()
    if s in _LANGUAGES:
        return "Programming Language"
    if s in _ML_AI:
        return "ML / AI"
    return "Tool / Platform"


_CATEGORY_COLOURS = {
    "Programming Language": "#1f77b4",  # blue
    "ML / AI":              "#2ca02c",  # green
    "Tool / Platform":      "#ff7f0e",  # orange
}


# -- Role categorisation --

_ROLE_RULES = [
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


def _categorise_title(title: str) -> str:
    if not isinstance(title, str):
        return "Other"
    t = title.lower()
    for label, patterns in _ROLE_RULES:
        for p in patterns:
            if re.search(p, t):
                return label
    return "Other"


# -- Salary parsing --

_SALARY_RE = re.compile(
    r"([\d,]+)\s*[–\-~to]+\s*([\d,]+)", flags=re.IGNORECASE,
)


def _parse_salary_range(s: str) -> tuple[int, int] | None:
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


# -- Experience bucketing --

def _experience_bucket(years: float) -> str:
    y = float(years) if pd.notna(years) else 0.0
    if y < 2:
        return "0-2 yrs"
    if y < 5:
        return "2-5 yrs"
    if y < 8:
        return "5-8 yrs"
    return "8+ yrs"


_EXP_ORDER = ["0-2 yrs", "2-5 yrs", "5-8 yrs", "8+ yrs"]


# -- Data loading --

@st.cache_data(show_spinner="Loading job market data...")
def load_jobs(path: str) -> pd.DataFrame:
    df = pd.read_csv(path).fillna("")

    df["role_category"] = df["job_title"].apply(_categorise_title)

    exp_col = pd.to_numeric(df.get("experience_years", 0), errors="coerce").fillna(0)
    df["exp_years_num"] = exp_col
    df["experience_bucket"] = exp_col.apply(_experience_bucket)

    parsed = df["salary_range"].apply(_parse_salary_range)
    df["salary_min"] = parsed.apply(lambda t: t[0] if t else None)
    df["salary_max"] = parsed.apply(lambda t: t[1] if t else None)
    df["salary_mid"] = df[["salary_min", "salary_max"]].mean(axis=1)

    return df


@st.cache_data(show_spinner=False)
def compute_skill_counts(job_skill_strings: tuple[str, ...]) -> pd.DataFrame:
    counter: Counter[str] = Counter()
    for s in job_skill_strings:
        if not s:
            continue
        counter.update(extract_skills(s))
    if not counter:
        return pd.DataFrame(columns=["skill", "count", "category"])
    rows = [
        {"skill": k, "count": v, "category": _skill_category(k)}
        for k, v in counter.items()
    ]
    return pd.DataFrame(rows).sort_values("count", ascending=False).reset_index(drop=True)


# -- Page render --

if not JOBS_PATH.exists():
    st.error(f"Job data not found at `{JOBS_PATH}`. Run the collector from the main page first.")
    st.stop()

jobs = load_jobs(str(JOBS_PATH))

st.title("Riyadh Tech Job Market Dashboard")
st.caption(
    "Analytics over **{:,}** live job listings from **{:,}** unique companies.".format(
        len(jobs), jobs["company"].nunique()
    )
)

st.divider()


# -- Section 1: Top skills --

st.subheader("Top 15 Most In-Demand Skills")

skill_counts = compute_skill_counts(tuple(jobs["required_skills"].tolist()))
top_skills = skill_counts.head(15).iloc[::-1]  # reverse so highest renders at top

if top_skills.empty:
    st.info("No skills detected in the current dataset.")
else:
    fig_skills = px.bar(
        top_skills,
        x="count",
        y="skill",
        color="category",
        color_discrete_map=_CATEGORY_COLOURS,
        orientation="h",
        labels={"count": "Number of jobs requiring this skill", "skill": ""},
    )
    fig_skills.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_skills, use_container_width=True)

st.divider()


# -- Section 2 + 3: Role distribution + Experience --

col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Jobs by Role Category")
    role_counts = (
        jobs["role_category"]
        .value_counts()
        .rename_axis("role")
        .reset_index(name="count")
    )
    fig_roles = px.pie(
        role_counts,
        names="role",
        values="count",
        hole=0.5,
    )
    fig_roles.update_traces(textposition="outside", textinfo="label+percent")
    fig_roles.update_layout(
        height=460,
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
    )
    st.plotly_chart(fig_roles, use_container_width=True)

with col_b:
    st.subheader("Experience Requirements")
    exp_counts = (
        jobs["experience_bucket"]
        .value_counts()
        .reindex(_EXP_ORDER, fill_value=0)
        .rename_axis("bucket")
        .reset_index(name="count")
    )
    fig_exp = px.bar(
        exp_counts,
        x="bucket",
        y="count",
        labels={"bucket": "Years of experience required", "count": "Jobs"},
        color="bucket",
        color_discrete_sequence=px.colors.sequential.Blues_r,
    )
    fig_exp.update_layout(
        height=460,
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
    )
    st.plotly_chart(fig_exp, use_container_width=True)

st.divider()


# -- Section 4: Salary by role --

st.subheader("Salary Range by Role Category")

salary_df = jobs[jobs["salary_mid"].notna()].copy()

if salary_df.empty:
    st.info("No parseable salary ranges in the current dataset.")
else:
    salary_by_role = (
        salary_df.groupby("role_category")
        .agg(
            avg_min=("salary_min", "mean"),
            avg_max=("salary_max", "mean"),
            job_count=("salary_min", "count"),
        )
        .reset_index()
        .sort_values("avg_max", ascending=True)
    )
    salary_by_role["avg_min"] = salary_by_role["avg_min"].round(0)
    salary_by_role["avg_max"] = salary_by_role["avg_max"].round(0)

    fig_salary = go.Figure()
    fig_salary.add_trace(go.Bar(
        y=salary_by_role["role_category"],
        x=salary_by_role["avg_min"],
        name="Avg. min salary",
        orientation="h",
        marker_color="#7fb3d5",
        hovertemplate="Min: %{x:,.0f} SAR<extra></extra>",
    ))
    fig_salary.add_trace(go.Bar(
        y=salary_by_role["role_category"],
        x=salary_by_role["avg_max"] - salary_by_role["avg_min"],
        name="Avg. max salary",
        orientation="h",
        marker_color="#1f77b4",
        base=salary_by_role["avg_min"],
        hovertemplate="Max: %{customdata:,.0f} SAR<extra></extra>",
        customdata=salary_by_role["avg_max"],
    ))
    fig_salary.update_layout(
        barmode="stack",
        height=420,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title="Monthly salary (SAR)",
        yaxis_title="",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_salary, use_container_width=True)
    st.caption(
        "Based on **{:,}** listings with structured salary ranges. "
        "Bars span the average min-to-max range per role category.".format(len(salary_df))
    )

st.divider()


# -- Section 5: Top hiring companies --

st.subheader("Top 15 Hiring Companies")

top_companies = (
    jobs[jobs["company"].str.strip() != ""]["company"]
    .value_counts()
    .head(15)
    .iloc[::-1]
    .rename_axis("company")
    .reset_index(name="count")
)

if top_companies.empty:
    st.info("No company data available.")
else:
    fig_companies = px.bar(
        top_companies,
        x="count",
        y="company",
        orientation="h",
        labels={"count": "Number of listings", "company": ""},
        color="count",
        color_continuous_scale="Blues",
    )
    fig_companies.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=10, b=10),
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig_companies, use_container_width=True)

st.divider()
st.caption(
    "Data source: `data/processed/jobs_clean.csv`. "
    "Refresh from the main page's **Collect Real Jobs** button."
)
