"""
utils.py - Text preprocessing, skill extraction, and resume parsing.
"""
from __future__ import annotations
import re
import string
from pathlib import Path
from typing import List, Set, Dict

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


# Skill vocabulary with aliases
# Each canonical skill maps to a list of regex patterns that should match it.
SKILL_ALIASES: Dict[str, List[str]] = {
    "python":       [r"\bpython\b"],
    "r":            [r"\br\b"],
    "java":         [r"\bjava\b"],
    "javascript":   [r"javascript", r"(?<![\w.])js\b"],
    "typescript":   [r"typescript"],
    "c++":          [r"c\+\+", r"\bcpp\b"],
    "c#":           [r"c#", r"csharp"],
    "scala":        [r"\bscala\b"],
    "rust":         [r"\brust\b"],
    "go":           [r"\bgo\b", r"golang"],
    "php":          [r"\bphp\b"],
    "ruby":         [r"\bruby\b"],
    "swift":        [r"\bswift\b"],
    "kotlin":       [r"\bkotlin\b"],
    "matlab":       [r"matlab"],
    "bash":         [r"\bbash\b", r"shell.script"],
    "fastapi":      [r"fastapi", r"fast.api"],
    "flask":        [r"\bflask\b"],
    "django":       [r"django"],
    "streamlit":    [r"streamlit"],
    "next.js":      [r"next\.?js", r"nextjs"],
    "react":        [r"\breact\b", r"reactjs"],
    "node.js":      [r"node\.?js", r"nodejs"],
    "rest api":     [r"rest.?api", r"restful"],
    "graphql":      [r"graphql"],
    "sql":          [r"\bsql\b"],
    "mysql":        [r"mysql"],
    "postgresql":   [r"postgresql", r"postgres"],
    "mongodb":      [r"mongodb", r"\bmongo\b"],
    "nosql":        [r"nosql"],
    "oracle":       [r"\boracle\b"],
    "sql server":   [r"sql.server", r"mssql"],
    "redis":        [r"\bredis\b"],
    "elasticsearch": [r"elasticsearch"],
    "spark":        [r"\bspark\b", r"pyspark"],
    "hadoop":       [r"hadoop"],
    "hive":         [r"\bhive\b"],
    "kafka":        [r"\bkafka\b"],
    "airflow":      [r"airflow"],
    "dbt":          [r"\bdbt\b"],
    "etl":          [r"\betl\b"],
    "snowflake":    [r"snowflake"],
    "bigquery":     [r"bigquery", r"big.query"],
    "redshift":     [r"redshift"],
    "machine learning":     [r"machine.learning", r"\bml\b"],
    "deep learning":        [r"deep.learning"],
    "nlp":                  [r"\bnlp\b", r"natural.language.processing"],
    "computer vision":      [r"computer.vision"],
    "ai":                   [r"\bai\b", r"artificial.intelligence"],
    "tensorflow":           [r"tensorflow"],
    "pytorch":              [r"pytorch", r"\btorch\b"],
    "keras":                [r"\bkeras\b"],
    "scikit-learn":         [r"scikit.learn", r"sklearn"],
    "xgboost":              [r"xgboost"],
    "lightgbm":             [r"lightgbm"],
    "bert":                 [r"\bbert\b"],
    "gpt":                  [r"\bgpt\b"],
    "llm":                  [r"\bllms?\b", r"large.language.model"],
    "transformers":         [r"\btransformers?\b", r"hugging.face"],
    "prompt engineering":   [r"prompt.engineering"],
    "feature engineering":  [r"feature.engineering"],
    "model deployment":     [r"model.deploy"],
    "rag":                  [r"\brag\b", r"retrieval.augmented"],
    "data science":         [r"data.scien"],
    "data analysis":        [r"data.analy"],
    "data engineering":     [r"data.engineer"],
    "data visualization":   [r"data.viz", r"data.visuali"],
    "statistics":           [r"statistic"],
    "mathematics":          [r"mathematic"],
    "a/b testing":          [r"a.?b.test"],
    "time series":          [r"time.series"],
    "forecasting":          [r"forecast"],
    "pandas":       [r"\bpandas\b"],
    "numpy":        [r"\bnumpy\b"],
    "matplotlib":   [r"matplotlib"],
    "seaborn":      [r"seaborn"],
    "plotly":       [r"plotly"],
    "opencv":       [r"opencv"],
    "scipy":        [r"scipy"],
    "power bi":     [r"power.bi", r"powerbi"],
    "tableau":      [r"tableau"],
    "excel":        [r"\bexcel\b"],
    "looker":       [r"\blooker\b"],
    "qlik":         [r"\bqlik\b"],
    "aws":          [r"\baws\b", r"amazon.web.service"],
    "azure":        [r"\bazure\b"],
    "google cloud": [r"google.cloud", r"\bgcp\b"],
    "docker":       [r"\bdocker\b"],
    "kubernetes":   [r"kubernetes", r"\bk8s\b"],
    "terraform":    [r"terraform"],
    "git":          [r"\bgit\b", r"\bgithub\b", r"\bgitlab\b"],
    "ci/cd":        [r"ci.?cd", r"continuous.integrat", r"continuous.deliver"],
    "linux":        [r"\blinux\b", r"\bubuntu\b"],
    "web scraping": [r"web.scrap", r"beautifulsoup", r"scrapy"],
    "selenium":     [r"selenium"],
    "playwright":   [r"playwright"],
    "communication":    [r"communicat"],
    "teamwork":         [r"teamwork", r"team.work", r"team.player"],
    "problem solving":  [r"problem.solv"],
    "critical thinking": [r"critical.think"],
    "leadership":       [r"leadership"],
    "project management": [r"project.manage"],
    "agile":            [r"\bagile\b"],
    "scrum":            [r"\bscrum\b"],
    "sap":          [r"\bsap\b"],
    "salesforce":   [r"salesforce"],
    "cybersecurity": [r"cybersecurity", r"cyber.security", r"infosec", r"information.security"],
    "siem":         [r"\bsiem\b"],
    "network security": [r"network.security"],
    "threat intelligence": [r"threat.intelligen"],
    "penetration testing": [r"penetration.test", r"pen.test"],
    "product management": [r"product.manage"],
    "data warehouse":     [r"data.warehous"],
    "microservices":      [r"microservice"],
    "api":                [r"\bapis?\b"],
}

# Flat list of canonical skill names (for UI dropdowns)
SKILLS_VOCAB: List[str] = sorted(SKILL_ALIASES.keys())

# Pre-compile all patterns
_COMPILED_PATTERNS: List[tuple] = []
for _skill, _patterns in SKILL_ALIASES.items():
    for _pat in _patterns:
        _COMPILED_PATTERNS.append((_skill, re.compile(_pat, re.IGNORECASE)))


def extract_skills(text: str) -> List[str]:
    """
    Extract skills from text using pattern matching with aliases.
    Returns deduplicated list of canonical skill names found.
    """
    if not isinstance(text, str) or not text.strip():
        return []

    found: Set[str] = set()
    text_lower = text.lower()

    for skill, pattern in _COMPILED_PATTERNS:
        if skill in found:
            continue
        if pattern.search(text_lower):
            found.add(skill)

    return sorted(found)


# -- Text cleaning --

def clean_cv_text(text: str) -> str:
    """
    Clean raw CV text from PDF extraction.
    """
    if not isinstance(text, str):
        return ""

    # Strip pdfplumber (cid:NNN) glyph placeholders — these appear where the
    # PDF embeds characters via a custom font mapping (bullets, arrows, etc.)
    # Leaving them in pollutes the embedding input with noise tokens.
    text = re.sub(r'\(cid:\d+\)', ' ', text)

    # Remove non-printable chars (keep newlines and tabs)
    text = re.sub(r'[^\x20-\x7E\n\t\r]', ' ', text)

    # Remove standalone page numbers
    text = re.sub(r'\n\s*\d{1,3}\s*\n', '\n', text)
    text = re.sub(r'\bpage\s*\d+\s*(of\s*\d+)?\b', '', text, flags=re.IGNORECASE)

    # Remove repeated special characters (decorative lines)
    text = re.sub(r'[-_=*#]{4,}', ' ', text)

    # Normalize whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Remove very short lines that are likely artifacts
    lines = text.split('\n')
    lines = [line for line in lines if len(line.strip()) > 2 or line.strip() == '']
    text = '\n'.join(lines)

    return text.strip()


# -- CV section splitting --

# Map of recognised header phrases → canonical bucket. Case-insensitive.
# Anything not matched ends up in "other".
_CV_SECTION_HEADERS: Dict[str, str] = {
    "skills":                 "skills",
    "technical skills":       "skills",
    "core skills":            "skills",
    "key skills":             "skills",
    "experience":             "experience",
    "work experience":        "experience",
    "professional experience": "experience",
    "employment":             "experience",
    "employment history":     "experience",
    "education":              "education",
    "academic background":    "education",
    "summary":                "other",
    "profile":                "other",
    "projects":               "other",
    "certifications":         "other",
}

# A line is a header only if the trimmed line *equals* one of the phrases
# above (optionally followed by ":" or a few trailing chars). This avoids
# matching sentences like "Experience with Python".
_HEADER_LINE_RE = re.compile(
    r"^\s*(" + "|".join(re.escape(h) for h in _CV_SECTION_HEADERS) + r")\s*:?\s*$",
    re.IGNORECASE,
)


def split_cv_sections(text: str) -> Dict[str, str]:
    """
    Split a CV into canonical sections by detecting common header lines.

    Returns a dict with exactly these keys:
        "skills", "experience", "education", "other"
    Missing sections map to "".  Text that appears before the first
    recognised header (name, contact info, etc.) goes into "other".
    """
    sections: Dict[str, List[str]] = {
        "skills":     [],
        "experience": [],
        "education":  [],
        "other":      [],
    }
    if not isinstance(text, str) or not text.strip():
        return {k: "" for k in sections}

    current = "other"
    for raw_line in text.splitlines():
        m = _HEADER_LINE_RE.match(raw_line)
        if m:
            header = m.group(1).lower()
            current = _CV_SECTION_HEADERS[header]
            continue
        sections[current].append(raw_line)

    return {k: "\n".join(v).strip() for k, v in sections.items()}


def prepare_cv_for_embedding(cv_text: str) -> str:
    """
    Prepare CV text for semantic embedding with Nomic task prefix.

    Strategy: split the CV into sections and reorder so the most
    relevant content (skills, then experience) comes first. This puts
    high-signal tokens near the start where the embedding model's
    attention is strongest. The remainder (education + other) follows.

    Nomic-embed-text-v1.5 expects "search_query: " for query-side text
    and supports up to 8192 tokens — no truncation needed for resumes.
    """
    cleaned = clean_cv_text(cv_text)
    sections = split_cv_sections(cleaned)

    ordered_parts: List[str] = []
    if sections["skills"]:
        ordered_parts.append("Skills: " + sections["skills"])
    if sections["experience"]:
        ordered_parts.append("Experience: " + sections["experience"])
    if sections["education"]:
        ordered_parts.append("Education: " + sections["education"])
    if sections["other"]:
        ordered_parts.append(sections["other"])

    body = "\n".join(ordered_parts) if ordered_parts else cleaned
    body = re.sub(r'\s+', ' ', body).strip()
    return "search_query: " + body


def prepare_job_for_embedding(job_row) -> str:
    """
    Build a clean text representation of a job for embedding with Nomic
    task prefix. Nomic-embed-text-v1.5 expects "search_document: " for
    document-side text and supports up to 8192 tokens.
    """
    parts = []
    title = str(job_row.get("job_title", "")).strip()
    if title:
        parts.append(title)
    desc = str(job_row.get("description", "")).strip()
    if desc:
        parts.append(desc)
    skills = str(job_row.get("required_skills", "")).strip()
    if skills:
        parts.append("Required skills: " + skills)
    text = ". ".join(parts)
    return "search_document: " + text


def extract_years_from_text(text: str) -> int:
    """Extract the largest year-of-experience number from text."""
    if not isinstance(text, str):
        return 0
    matches = re.findall(r'(\d+)\s*\+?\s*(?:years?|yrs?)', text.lower())
    candidates = [int(m) for m in matches if 0 <= int(m) <= 30]
    return max(candidates, default=0)


# -- File parsing --

def parse_pdf(filepath: str) -> str:
    """Extract and clean text from a PDF resume."""
    if pdfplumber is None:
        raise ImportError("pdfplumber is not installed. Run: pip install pdfplumber")
    try:
        with pdfplumber.open(filepath) as pdf:
            pages = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    pages.append(page_text)
        raw = "\n\n".join(pages)
        return clean_cv_text(raw)
    except Exception as exc:
        raise ValueError("Failed to parse PDF: " + str(exc)) from exc


def parse_text(filepath: str) -> str:
    """Read a plain-text resume file."""
    try:
        raw = Path(filepath).read_text(encoding="utf-8", errors="ignore")
        return clean_cv_text(raw)
    except Exception as exc:
        raise ValueError("Failed to read text file: " + str(exc)) from exc
