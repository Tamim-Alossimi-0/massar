# Saudi Resume-Job Matcher

An AI-powered tool that matches CVs against Saudi tech job listings using semantic similarity and skill analysis. Upload a resume, the system ranks live Riyadh job postings by how well they fit the candidate, and explains why each match scored the way it did.

---

## Features

- **Semantic matching with Nomic-embed-text-v1.5** — 768-dimensional embeddings with an 8192-token context window, using Nomic's `search_query` / `search_document` task prefixes.
- **4-signal hybrid scoring** — combines:
  - Semantic cosine similarity (40%)
  - Direct skill overlap with required-vs-description weighting (35%)
  - TF-IDF cosine similarity over 1-2 grams (15%)
  - Experience-years match (10%)
- **100+ skill extraction patterns** with alias support (e.g. `js` -> `javascript`, `k8s` -> `kubernetes`) and acronym guards to prevent false positives.
- **Section-aware CV parsing** — resumes are split into Skills / Experience / Education / Other and reordered (skills first, experience second) before embedding, so the query vector emphasises the most discriminative content.
- **GPU-accelerated** — CUDA-enabled PyTorch for fast embedding on NVIDIA GPUs; falls back to CPU transparently.
- **Seniority filtering** — Entry / Junior / Mid / Senior ranges with senior-title exclusion for entry-level searches.
- **Disk-cached embeddings** — first startup encodes the full corpus (~7 min on 1400 jobs); subsequent startups load from disk in under a second. Caches auto-invalidate when the underlying CSV changes.
- **Interactive Streamlit UI** — skill verification multiselect, keyword search, salary / experience display, downloadable CSV of matches, and per-job match explanations.

---

## Tech Stack

- **Python 3.11**
- **Streamlit** — web UI
- **Sentence Transformers** with **Nomic Embed** — semantic embeddings
- **scikit-learn** — TF-IDF and cosine similarity
- **PyTorch** (CUDA 12.1) — GPU acceleration
- **pdfplumber** — PDF resume parsing
- **Playwright** — Jadarat.sa scraping
- **python-jobspy** — LinkedIn scraping

---

## Installation

```bash
git clone <repo-url>
cd saudi-resume-job-matcher

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

**Install PyTorch with CUDA 12.1 (recommended for NVIDIA GPUs):**

```bash
pip install torch==2.2.2 --index-url https://download.pytorch.org/whl/cu121
```

For CPU-only systems, use the CPU wheel instead:

```bash
pip install torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu
```

**Install Playwright browser (for Jadarat scraping):**

```bash
python -m playwright install chromium
```

---

## Usage

Start the Streamlit app:

```bash
streamlit run app.py
```

The app opens in your browser. Upload a PDF or TXT resume, verify the auto-detected skills, and the top matches are ranked instantly.

To refresh the job dataset with live Riyadh listings, click **Collect Real Jobs** in the sidebar. The collector tries Jadarat first, falls back to LinkedIn, then Bayt, and only uses synthetic data as a last resort.

Run the test suite:

```bash
pytest tests/
```

Run the offline evaluator:

```bash
python evaluator.py
```

---

## Project Structure

| File | Responsibility |
|---|---|
| `app.py` | Streamlit UI — upload widget, sidebar filters, result cards, CSV export |
| `model.py` | Core matching engine — embeddings, TF-IDF, skill scoring, experience scoring, explanation generation, disk cache |
| `utils.py` | Text preprocessing, skill extraction vocabulary + regex patterns, CV section splitter, PDF parser |
| `scraper.py` | Data pipeline orchestrator — Jadarat -> LinkedIn -> Bayt -> synthetic fallback |
| `jadarat_collector.py` | Playwright-based scraper for jadarat.sa |
| `linkedin_collector.py` | LinkedIn collector via python-jobspy (20-keyword sweep across Riyadh) |
| `evaluator.py` | Offline benchmark against 10 labelled CV / job pairs |
| `tests/test_matching.py` | Unit tests for skill extraction and matching pipeline |
| `data/processed/jobs_clean.csv` | Canonical job dataset |
| `data/embeddings_cache/` | Disk cache for job embeddings (`.npy`) and TF-IDF matrix (`.joblib`) with metadata |

---

## How Matching Works

Given a CV and a filtered set of jobs, the engine runs four independent scoring signals, combines them by fixed weights, and returns the top N.

**1. Semantic similarity (40%)**
The CV is split into sections, reordered (skills first), prefixed with Nomic's `search_query:` token, and embedded. Jobs are embedded once at startup (cached on disk) with the `search_document:` prefix. Cosine similarity between the CV vector and each job vector gives the semantic score.

**2. Skill overlap (35%)**
Both CV and job text are scanned for 100+ known skills using alias-aware regex. Required skills (from the `required_skills` column) count double; skills mentioned only in the description count single. The score is weighted-matched divided by weighted-total.

**3. TF-IDF cosine similarity (15%)**
A TF-IDF vectorizer is fit on the full job corpus at startup (cached to disk via joblib) with 1-2 grams, English stopwords, and `min_df=2`. The CV is transformed with the same vocabulary and cosine-compared to each job. This catches lexical overlap that the semantic model may downweight.

**4. Experience match (10%)**
Years are extracted from the job description (e.g. "3+ years of Python") and compared to the user's input years. The score is `min(user_years / job_years, 1.0)`; jobs with no stated requirement score 1.0 when the user provides experience, 0.8 otherwise.

The four scores are combined: `overall = 0.40 * semantic + 0.35 * skills + 0.15 * tfidf + 0.10 * experience`. Results are sorted by overall score and the top N are returned with a per-job explanation summarising which signals drove the match.

---

## Data Sources

The collector orchestrates three real sources with a synthetic fallback:

1. **Jadarat.sa** — Saudi Arabia's official government jobs portal, scraped with Playwright. Cloudflare frequently blocks automated access, so this is a best-effort source.
2. **LinkedIn** — scraped via `python-jobspy` across 20 tech keywords (data scientist, software engineer, devops engineer, cybersecurity analyst, and more) with `results_wanted=100` per keyword. Results are Riyadh-filtered, normalised to the canonical schema, and deduplicated by title + company.
3. **Bayt.com** — HTTP + BeautifulSoup scrape of bayt.com search results.
4. **Synthetic fallback** — 1000 deterministic tech jobs generated across 7 sectors with title-aware experience-year ranges. Used only when all real sources fail.

Real listings take priority over synthetic on dedup: when a LinkedIn row shares a title + company key with a synthetic row, the real row is kept. The merged dataset is written to `data/processed/jobs_clean.csv`.

---

## Performance

On an RTX 4060 with 1387 jobs:

| Operation | Time |
|---|---|
| First startup (encode + TF-IDF fit) | ~7 minutes |
| Subsequent startup (disk cache hit) | < 1 second |
| Single CV match (top 10) | ~2 seconds |

---

## License

MIT
