---
title: Massar API
emoji: 🎯
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Massar | مسار

AI-powered career matching platform that connects job seekers with tech roles in Saudi Arabia using semantic analysis and skill matching.

## What it does

Upload your CV and Massar ranks it against 1,300+ real tech job listings scraped from LinkedIn across Saudi Arabia. You get a ranked list of the best-fit roles, a breakdown of which skills matched and which are missing, estimated salary ranges for the matched positions, and targeted recommendations for closing the gap between your profile and the roles you want.

## How matching works

Every CV is scored against every job using a 4-signal hybrid pipeline. The weights were tuned on a held-out set of labeled CV / job pairs.

- Semantic similarity (40%) — Nomic-embed-text-v1.5 produces 768-dimensional embeddings for both CV and job description; cosine similarity captures meaning beyond exact keyword overlap.
- Skill overlap (35%) — 100+ skill patterns with alias matching (js -> javascript, k8s -> kubernetes). Required skills count double versus skills that merely appear in the description.
- TF-IDF keyword matching (15%) — 1-2 gram vectorizer catches exact terminology and niche tools the embeddings sometimes smooth over.
- Experience fit (10%) — candidate years are compared against the job's required range, with soft penalties for over- and under-qualification.

The CV is first parsed into sections (Skills, Experience, Education, Other) and reordered so the most discriminative content sits at the top of the embedded text.

## Tech stack

Frontend: Next.js, Tailwind CSS, shadcn/ui, Recharts
Backend: FastAPI, Python 3.10+
ML / NLP: Sentence Transformers, Nomic Embed, scikit-learn
Data: LinkedIn scraping via python-jobspy, PDF parsing via pdfplumber

## Features

- Real-time CV parsing and skill extraction from PDF or TXT
- Section-aware CV processing with Skills / Experience / Education reordering
- Career gap report with salary estimates and targeted skill recommendations
- Interactive skill demand visualization across matched roles
- Side-by-side job comparison
- Market dashboard with hiring trends and top employers
- GPU-accelerated matching with automatic CPU fallback
- Try Demo button for an instant preview without uploading a CV

## Getting started

Clone the repo:

```bash
git clone https://github.com/Tamim-Alossimi-0/saudi-resume-job-matcher.git
cd saudi-resume-job-matcher
```

Run the backend:

```bash
pip install -r requirements.txt
uvicorn api:app --port 8000
```

Run the frontend in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 and upload a CV, or click Try Demo.

GPU users: install a CUDA-enabled PyTorch build before `pip install -r requirements.txt`, following the selector at https://pytorch.org/get-started/locally/. The embedding pipeline automatically uses CUDA when available and falls back to CPU otherwise.

## Project structure

```
saudi-resume-job-matcher/
├── api.py                  FastAPI app, endpoints, lifespan priming
├── model.py                Embedding, TF-IDF, scoring, ranking pipeline
├── utils.py                Skill vocabulary, aliases, PDF / text parsing
├── scraper.py              Scraper orchestration
├── linkedin_collector.py   LinkedIn collector via python-jobspy
├── gap_report.py           Skill gap and salary recommendations
├── frontend/               Next.js app (pages, components, lib)
├── data/
│   └── processed/
│       └── jobs_clean.csv  1,387-row cleaned job dataset
└── requirements.txt
```

Pre-computed embedding and TF-IDF caches live under `data/embeddings_cache/` and ship with the repo so cold starts are under a second.

## Author

Tamim Khalid Alossimi
