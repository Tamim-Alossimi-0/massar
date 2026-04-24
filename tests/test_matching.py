"""
tests/test_matching.py — Unit tests for the Saudi Resume-Job Matcher.
Run with: pytest tests/ -v
"""
from __future__ import annotations
import sys
from pathlib import Path

import pandas as pd
import pytest

# Make parent importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import clean_cv_text, extract_skills
from model import get_top_matches, score_breakdown


def test_clean_cv_text_cleans_pdf_artifacts():
    """
    clean_cv_text strips PDF artifacts (decorative lines, standalone page
    numbers, non-printable chars) and normalizes whitespace.  It does NOT
    lowercase or remove punctuation — case and punctuation must survive.
    """
    raw = "Skills\n------------\nPython, SQL\n  \n  2  \nMore content"
    result = clean_cv_text(raw)

    # Decorative dashes removed
    assert "----" not in result, "Decorative dash line should be stripped"
    # Content preserved
    assert "Python, SQL" in result, "Real content must be preserved"
    assert "More content" in result
    # Case preserved
    assert "Python" in result, "Case must be preserved (no lowercasing)"
    # Punctuation preserved
    assert "," in result, "Punctuation must be preserved"
    # Standalone page number dropped
    assert "\n  2  \n" not in result and "\n2\n" not in result
    # Returns a string
    assert isinstance(result, str)


def test_extract_skills_finds_python_and_sql():
    """extract_skills should detect Python and SQL in a sample text."""
    text = "I have 5 years of experience with Python, SQL, and Excel."
    skills = extract_skills(text)
    assert "python" in skills, "Expected 'python' to be extracted"
    assert "sql" in skills, "Expected 'sql' to be extracted"


def test_get_top_matches_returns_five_rows():
    """get_top_matches should return a DataFrame with exactly 5 rows by default."""
    # Build a minimal jobs DataFrame with 10 rows
    jobs = pd.DataFrame([
        {
            "job_title": f"Job {i}",
            "company": "Acme",
            "location": "Riyadh",
            "description": f"Looking for Python SQL developer with {i+1} years experience.",
            "required_skills": "Python, SQL",
            "experience_level": "Mid Level",
            "salary": "Confidential",
        }
        for i in range(10)
    ])
    cv_text = "Python developer with 4 years of SQL and machine learning experience."
    result = get_top_matches(cv_text, jobs, full_df=jobs, top_n=5)
    assert isinstance(result, pd.DataFrame), "Result must be a DataFrame"
    assert len(result) == 5, f"Expected 5 rows, got {len(result)}"


def test_score_breakdown_returns_correct_keys():
    """score_breakdown must return a dict with semantic_score, skills_score, experience_score."""
    cv = "Python developer, 3 years experience, SQL, Machine Learning"
    job = "We need a Python developer with 2 years experience and SQL skills"
    result = score_breakdown(cv, job)
    assert isinstance(result, dict), "score_breakdown must return a dict"
    assert "semantic_score" in result, "Missing key: semantic_score"
    assert "skills_score" in result, "Missing key: skills_score"
    assert "experience_score" in result, "Missing key: experience_score"
