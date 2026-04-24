"""
app.py - Saudi Resume-Job Matcher - Streamlit UI
Run: streamlit run app.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from utils import parse_pdf, parse_text, extract_skills, SKILLS_VOCAB
from model import (
    load_jobs, get_top_matches, filter_by_location,
    prime_embeddings, SENIORITY_YEAR_RANGES,
)
from gap_report import generate_gap_report

JOBS_PATH = "data/processed/jobs_clean.csv"

st.set_page_config(page_title="Saudi Resume-Job Matcher", layout="wide")

st.title("Saudi Resume-Job Matcher")
st.caption("Semantic matching + Skill overlap scoring - Powered by Sentence Transformers")

# -- Sidebar --
with st.sidebar:
    st.header("Filters")

    user_experience_years = st.number_input(
        "Your Experience (Years)",
        min_value=0, max_value=40, value=1, step=1,
        help="Used to score experience match against job requirements",
    )

    seniority_label = st.selectbox(
        "Seniority Level",
        options=list(SENIORITY_YEAR_RANGES.keys()),
        index=0,
        help="Filters jobs by experience range. Entry/Junior excludes Senior titles.",
    )

    keyword_search = st.text_input(
        "Search by Title or Company",
        placeholder="e.g. Data Scientist, Aramco",
    )

    top_n = st.slider("Number of Results", 1, 20, 10)

    st.divider()
    st.subheader("Job Data")
    if st.button("Collect Real Jobs", use_container_width=True,
                 help="Tries Jadarat -> LinkedIn -> Bayt. Falls back to synthetic only if all real sources fail."):
        with st.spinner("Collecting real jobs (Jadarat -> LinkedIn -> Bayt, synthetic only as fallback)..."):
            try:
                from scraper import collect_jobs
                collect_jobs()
                st.cache_data.clear()
                st.success("Job data refreshed!")
            except Exception as exc:
                st.error("Refresh failed: {}".format(exc))


# -- Load jobs --
@st.cache_data(show_spinner="Loading job database...")
def _load(path):
    try:
        return load_jobs(path)
    except FileNotFoundError:
        st.warning("No job data found. Click **Collect Real Jobs** in the sidebar.")
        return pd.DataFrame()


jobs_df = _load(JOBS_PATH)

if not jobs_df.empty:
    with st.spinner("Loading AI model & encoding jobs (first time only)..."):
        prime_embeddings(jobs_df, csv_path=JOBS_PATH)

# -- Apply pre-search filters --
filtered = filter_by_location(jobs_df, "Riyadh")

if keyword_search.strip():
    kw = keyword_search.strip().lower()
    filtered = filtered[
        filtered["job_title"].str.lower().str.contains(kw, na=False, regex=False) |
        filtered["company"].str.lower().str.contains(kw, na=False, regex=False)
    ]

with st.sidebar:
    riyadh_count = len(filter_by_location(jobs_df, "Riyadh")) if not jobs_df.empty else 0
    st.caption("Dataset: **{}** jobs - **{}** in Riyadh".format(len(jobs_df), riyadh_count))
    st.caption("After filters: **{}** jobs".format(len(filtered)))


# -- CV Upload --
st.subheader("Upload Your CV")
uploaded = st.file_uploader("PDF or TXT", type=["pdf", "txt"])

if uploaded is not None:
    with st.spinner("Parsing CV..."):
        try:
            if Path(uploaded.name).suffix.lower() == ".pdf":
                tmp = Path("data/tmp_cv.pdf")
                tmp.parent.mkdir(parents=True, exist_ok=True)
                tmp.write_bytes(uploaded.read())
                cv_text = parse_pdf(str(tmp))
                tmp.unlink(missing_ok=True)
            else:
                cv_text = uploaded.read().decode("utf-8", errors="ignore")
        except Exception as exc:
            st.error("Failed to parse CV: {}".format(exc))
            st.stop()

    with st.expander("CV Text Preview", expanded=False):
        st.text(cv_text[:1500] + ("..." if len(cv_text) > 1500 else ""))

    detected_skills = sorted(extract_skills(cv_text))
    user_skills = st.multiselect(
        "Verify & Add Your Skills",
        options=sorted(SKILLS_VOCAB),
        default=detected_skills,
        help="Skills auto-detected from your CV. Add any that were missed, or remove incorrect ones.",
    )
    cv_skills_set = set(user_skills)

    st.divider()

    if filtered.empty:
        st.warning("No jobs match the current filters.")
        st.stop()

    eff_n = min(top_n, len(filtered))
    with st.spinner("Matching your CV against {} jobs...".format(len(filtered))):
        matches = get_top_matches(
            cv_text,
            filtered,
            full_df=jobs_df,
            top_n=eff_n,
            user_experience_years=user_experience_years,
            user_skills=user_skills,
            location=None,
            seniority_label=seniority_label,
        )

    if matches.empty:
        st.warning("No matches found. Try adjusting your filters.")
        st.stop()

    st.subheader("Top {} Matching Jobs".format(len(matches)))

    for rank, (_, row) in enumerate(matches.iterrows(), start=1):
        pct = "{:.1f}%".format(row["overall_score"] * 100)
        header = "#{} - **{}** at {} ({}) - {}".format(
            rank, row["job_title"], row["company"], row["location"], pct
        )

        with st.expander(header, expanded=(rank <= 3)):
            c1, c2, c3 = st.columns(3)
            c1.metric("Overall Match", pct)
            c2.metric("Skills Match", "{:.1f}%".format(row["skills_score"] * 100))
            c3.metric("Experience Match", "{:.1f}%".format(row["experience_score"] * 100))
            st.progress(float(row["overall_score"]))

            if row.get("match_explanation"):
                st.info("**{}**".format(row["match_explanation"]))

            d1, d2 = st.columns(2)
            if row.get("salary_range"):
                d1.markdown("**Salary:** {}".format(row["salary_range"]))
            if row.get("experience_years"):
                d2.markdown("**Required:** {} yrs - **You:** {} yrs".format(
                    row["experience_years"], user_experience_years
                ))

            skill_imp = {}
            try:
                skill_imp = json.loads(row.get("skill_importance", "{}") or "{}")
            except Exception:
                pass

            if cv_skills_set:
                st.markdown("**Your Skills for This Job**")
                tags = []
                for s in sorted(cv_skills_set):
                    imp = skill_imp.get(s)
                    if imp == "high":
                        color, label = "#d62728", "required"
                    elif imp in ("medium", "low"):
                        color, label = "#1f77b4", "relevant"
                    else:
                        color, label = "#7f7f7f", "not listed"
                    tags.append(
                        "<span style='background:{};color:white;"
                        "padding:2px 8px;border-radius:10px;"
                        "font-size:0.80em;margin:2px;display:inline-block'>"
                        "{} <span style='font-size:.72em;opacity:.85'>({})</span></span>".format(
                            color, s, label
                        )
                    )
                st.markdown(" ".join(tags), unsafe_allow_html=True)
                st.caption("Red = Required | Blue = Relevant | Grey = Not listed")

            st.divider()

            matched_list = [s for s in row["matched_skills"].split(", ") if s] if row.get("matched_skills") else []
            missing_list = [s for s in row["missing_skills"].split(", ") if s] if row.get("missing_skills") else []

            s1, s2 = st.columns(2)
            with s1:
                if matched_list:
                    st.markdown("**Matched Skills**")
                    for s in matched_list:
                        imp = skill_imp.get(s, "medium")
                        st.markdown("  {} ({})".format(s, imp))
            with s2:
                if missing_list:
                    st.markdown("**Skills to Add**")
                    for s in missing_list[:10]:
                        imp = skill_imp.get(s, "medium")
                        st.markdown("  {} ({})".format(s, imp))

    st.divider()
    st.download_button(
        "Download Matches as CSV",
        data=matches.to_csv(index=False).encode("utf-8"),
        file_name="job_matches.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # -- CV Gap Report --
    st.divider()
    st.subheader("Your CV Gap Report")

    report = generate_gap_report(
        matches_df=matches,
        cv_skills=user_skills,
        user_experience_years=int(user_experience_years),
        cv_text=cv_text,
    )

    if "error" in report:
        st.info(report["error"])
    else:
        # Profile summary card
        with st.container(border=True):
            st.markdown(
                "Based on your CV, you best match **{}** roles in Riyadh.".format(
                    report["top_role"]
                )
            )
            st.markdown(
                "You have **{} out of {}** commonly required skills for these roles.".format(
                    report["cv_skills_covered"], report["total_unique_skills"]
                )
            )
            st.markdown(
                "Your experience level: **{}** based on **{}** years.".format(
                    report["seniority"], report["experience_years"]
                )
            )

        # Skills you should learn
        st.markdown("### Skills You Should Learn")
        if not report["top_missing"]:
            st.success("Your CV already covers the common requirements for these roles.")
        else:
            _IMPORTANCE_COLOR = {
                "high":   "#d62728",  # red
                "medium": "#1f77b4",  # blue
                "low":    "#7f7f7f",  # grey
            }
            tag_html = []
            for item in report["top_missing"]:
                color = _IMPORTANCE_COLOR.get(item["importance"], "#1f77b4")
                tag_html.append(
                    "<span style='background:{c};color:white;padding:3px 10px;"
                    "border-radius:12px;font-size:0.85em;margin:3px;display:inline-block'>"
                    "{s} <span style='opacity:.8;font-size:.78em'>"
                    "(needed by {n} / {k}, {imp})</span></span>".format(
                        c=color, s=item["skill"],
                        n=item["jobs_requiring"], k=report["match_count"],
                        imp=item["importance"],
                    )
                )
            st.markdown(" ".join(tag_html), unsafe_allow_html=True)
            st.info(
                "Adding these skills could increase your average match score "
                "by approximately **{}%**.".format(report["estimated_boost_pct"])
            )

        # Salary expectations + experience gap side by side
        sal_col, exp_col = st.columns(2)

        with sal_col:
            st.markdown("### Salary Expectations")
            if report["salary"]:
                s = report["salary"]
                st.metric(
                    "Expected monthly range",
                    "{:,} - {:,} SAR".format(s["avg_min"], s["avg_max"]),
                )
                st.caption(
                    "Based on {} matched listings with structured salary data.".format(
                        s["sample_n"]
                    )
                )
            else:
                st.caption("No structured salary data in your matched listings.")

        with exp_col:
            st.markdown("### Experience Gap")
            if report["experience_gap"]:
                g = report["experience_gap"]
                st.warning(
                    "Most matching roles require **~{} years**. "
                    "You have **{} years**. Consider targeting **{}** tier roles first.".format(
                        g["avg_required"], g["user_has"], g["suggested_tier"]
                    )
                )
            else:
                st.success("Your experience is in line with the roles you matched.")

        # Downloadable plain-text report
        report_filename = "cv_gap_report_{}.txt".format(report["generated_on"])
        st.download_button(
            "Download Gap Report (TXT)",
            data=report["text_report"].encode("utf-8"),
            file_name=report_filename,
            mime="text/plain",
            use_container_width=True,
        )
