"""
scraper.py — Job data pipeline for the Saudi Resume-Job Matcher.

Data sources (tried in order):
  1. Jadarat.sa via Playwright browser automation
  2. Bayt.com via HTTP scraping
  3. Expanded synthetic dataset (1000 realistic Saudi tech jobs)

Run with: python scraper.py
"""
from __future__ import annotations
import csv
import random
import time
from itertools import cycle
from pathlib import Path
from typing import List, Dict

import requests
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None  # type: ignore

RAW_PATH = Path("data/raw/jobs.csv")
CLEAN_PATH = Path("data/processed/jobs_clean.csv")

FIELDNAMES = [
    "job_title", "company", "location", "description",
    "required_skills", "experience_years", "education", "salary_range",
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ══════════════════════════════════════════════════════════════════════════════
# SYNTHETIC DATA — 1000 realistic Saudi tech jobs across 7 sectors
# ══════════════════════════════════════════════════════════════════════════════

_COMPANIES = [
    "STC", "Saudi Aramco", "SABIC", "stc pay", "Noon", "Jarir", "Elm",
    "Takamol", "Ejada", "Lucidya", "Mozn", "Unifonic", "Foodics", "Tamara",
    "NEOM", "PIF", "Riyad Bank", "Al Rajhi Bank", "McKinsey Riyadh",
    "Deloitte KSA", "KPMG Saudi Arabia", "Accenture KSA", "IBM KSA",
    "Oracle KSA", "SAP Saudi Arabia", "Careem", "Salla", "Zid",
    "Tabby", "Geidea", "HungerStation", "Delivery Hero MENA",
    "Arab National Bank", "Banque Saudi Fransi", "Maaden",
    "Saudi Electricity Company", "Mobily", "Zain KSA", "stc Solutions",
    "Seera Group", "Dur Hospitality", "AlUla Development Authority",
    "National Water Company", "Saudi Post", "GOSI", "Monsha'at",
]
_LOCATIONS = ["Riyadh"]          # Riyadh-only dataset
_EDUCATION = ["Bachelor", "Master", "PhD"]

# ── Templates shared across all sectors ──────────────────────────────────────
_OPENING = [
    "We are seeking a talented {title} to join our growing team at {company} ({location}).",
    "{company} is hiring an experienced {title} to strengthen our {sector_label} capabilities in {location}.",
    "Join {company} as a {title} and help us drive innovation across {sector_label} in Saudi Arabia.",
    "An exciting opportunity at {company} for a skilled {title} based in {location}.",
    "{company}'s {sector_label} team is expanding and looking for a passionate {title} in {location}.",
]

_CLOSING = [
    "A {education}'s degree in a relevant field and {exp}+ years of experience are required.",
    "Candidates should hold a {education}'s degree with at least {exp} years of hands-on experience.",
    "We require a {education}'s degree and {exp}+ years of proven experience in a similar role.",
    "This role requires a {education}'s degree (or equivalent) and a minimum of {exp} years of relevant experience.",
    "A {education}'s degree with {exp}+ years of industry experience is expected. Saudi nationals and Iqama holders welcome.",
]

# ── Sector definitions ────────────────────────────────────────────────────────
_SECTORS = [
    # ── Data Science ──────────────────────────────────────────────────────────
    {
        "key": "data_science", "count": 155, "label": "Data Science",
        "titles": [
            "Data Scientist", "Senior Data Scientist", "Lead Data Scientist",
            "Applied Scientist", "Research Scientist", "Principal Data Scientist",
            "Data Science Specialist", "Staff Data Scientist",
        ],
        "skills_pool": [
            "Python, Machine Learning, Deep Learning, SQL, TensorFlow, PyTorch, Pandas, NumPy, Scikit-learn, Statistics, Feature Engineering, Git",
            "Python, NLP, BERT, Transformers, Hugging Face, SQL, Pandas, Feature Engineering, Model Deployment, FastAPI, Docker, Git",
            "Python, Machine Learning, XGBoost, LightGBM, Gradient Boosting, Statistics, Feature Engineering, Pandas, NumPy, SQL, Matplotlib, Git",
            "Python, Deep Learning, Computer Vision, OpenCV, PyTorch, TensorFlow, SQL, Pandas, Git, Docker, AWS",
            "Python, NLP, LLM, Prompt Engineering, GPT, Hugging Face, Transformers, SQL, Pandas, Statistics, Git, Azure",
            "Python, Machine Learning, A/B Testing, Statistics, SQL, Pandas, Scikit-learn, Matplotlib, Seaborn, Git, Airflow",
            "Python, Recommender Systems, Machine Learning, SQL, Spark, TensorFlow, Pandas, NumPy, Git, AWS, Docker",
            "Python, Time Series, Forecasting, Machine Learning, SQL, Pandas, NumPy, Statistics, Prophet, Git",
        ],
        "body_sentences": [
            "You will design and implement machine learning models to solve complex business problems and improve decision-making at scale.",
            "Working closely with data engineers, you will build robust feature pipelines that feed production ML systems.",
            "You will conduct rigorous experiments using statistical methods and present findings to senior stakeholders.",
            "The role involves owning the full ML lifecycle: from data exploration and feature engineering to model deployment and monitoring.",
            "You will apply advanced NLP and large language model techniques to Arabic and English text data at scale.",
            "Responsibilities include fine-tuning transformer models (BERT, GPT variants) for classification and generation tasks.",
            "Close collaboration with MLOps engineers to containerise and serve models via REST APIs is expected.",
            "You will build predictive models for customer retention, revenue forecasting, and product recommendations.",
            "Evaluating model performance with rigorous benchmarks and iterating rapidly using experiment tracking tools is a core activity.",
            "You will mentor junior data scientists and contribute to internal ML best-practices and knowledge sharing.",
            "Deep learning model optimisation, hyperparameter tuning, and cross-validation will be everyday activities.",
            "You will work on computer vision pipelines for image classification, object detection, and segmentation tasks.",
        ],
        "salary_range": ["18,000–25,000 SAR/month", "22,000–32,000 SAR/month", "28,000–42,000 SAR/month", "35,000–50,000 SAR/month"],
    },
    # ── ML / AI Engineering ───────────────────────────────────────────────────
    {
        "key": "ml_engineering", "count": 145, "label": "ML/AI Engineering",
        "titles": [
            "ML Engineer", "Senior ML Engineer", "MLOps Engineer",
            "AI Engineer", "Machine Learning Platform Engineer",
            "AI Solutions Engineer", "Senior AI Engineer", "ML Infrastructure Engineer",
        ],
        "skills_pool": [
            "Python, MLOps, Docker, Kubernetes, TensorFlow, PyTorch, Airflow, AWS, Git, CI/CD, MLflow",
            "Python, Machine Learning, Model Deployment, FastAPI, Docker, Kubernetes, AWS, Spark, SQL, Git",
            "Python, Deep Learning, TensorFlow, TensorFlow Serving, Docker, Kubernetes, Airflow, AWS, SQL, GitHub",
            "Python, AI, PyTorch, ONNX, FastAPI, Docker, Kubernetes, AWS, Azure, CI/CD, Git",
            "Python, MLOps, Kubeflow, MLflow, Docker, Kubernetes, Google Cloud, SQL, Airflow, Git",
            "Python, LLM, Langchain, FastAPI, Docker, AWS, Git, CI/CD, Hugging Face, PostgreSQL",
            "Python, Recommendation Systems, Real-time ML, Kafka, Spark, Docker, Kubernetes, AWS, SQL, Git",
        ],
        "body_sentences": [
            "You will design and maintain scalable ML infrastructure including automated training, evaluation, and deployment pipelines.",
            "Monitoring model drift, latency, and data quality in production will be a key part of your daily responsibilities.",
            "You will package models into production-grade services using FastAPI, TensorFlow Serving, or TorchServe.",
            "Designing feature stores, model registries, and inference endpoints that serve millions of predictions daily is expected.",
            "Responsibilities include optimising model latency, building shadow-testing frameworks, and automating A/B experiments.",
            "You will collaborate with data scientists to translate experimental notebooks into robust, production-ready services.",
            "Building and maintaining CI/CD pipelines for ML workflows using GitHub Actions, Jenkins, or similar tools is required.",
            "You will implement observability, alerting, and rollback mechanisms for all deployed ML models.",
            "Containerisation with Docker and orchestration with Kubernetes are core skills you will use daily.",
            "You will integrate LLM-powered features (RAG, function calling, agents) into our product stack.",
        ],
        "salary_range": ["20,000–30,000 SAR/month", "25,000–38,000 SAR/month", "32,000–48,000 SAR/month"],
    },
    # ── Data Analysis / BI ────────────────────────────────────────────────────
    {
        "key": "data_analysis_bi", "count": 150, "label": "Data Analysis & BI",
        "titles": [
            "Data Analyst", "Senior Data Analyst", "BI Developer",
            "Business Intelligence Analyst", "Reporting Analyst",
            "Analytics Engineer", "Product Analyst", "Growth Analyst",
            "Marketing Analyst", "Operations Analyst",
        ],
        "skills_pool": [
            "SQL, Power BI, Excel, Python, Tableau, DAX, Data Analysis, Data Visualization, ETL, Statistics",
            "SQL, Tableau, Python, Pandas, Data Visualization, Excel, BI, ETL, Statistics, Communication",
            "SQL Server, Power BI, DAX, ETL, Excel, Data Modeling, Python, Pandas, Statistics, Communication",
            "SQL, Python, Looker, dbt, Data Analysis, Data Visualization, ETL, Pandas, Statistics, Agile",
            "SQL, Google Sheets, Tableau, Python, Data Analysis, Excel, BI, Statistics, Communication",
            "SQL, Power BI, Python, A/B Testing, Statistics, Excel, Data Analysis, Google Sheets, Communication, Agile",
            "SQL, Mixpanel, Amplitude, Python, Data Analysis, Excel, Statistics, Communication, Product Analytics",
        ],
        "body_sentences": [
            "You will design and maintain interactive Power BI or Tableau dashboards consumed by executives and operational teams.",
            "Writing optimised SQL queries against our data warehouse and automating reports using Python will be regular activities.",
            "You will partner with business units to define KPIs, validate data quality, and document data lineage.",
            "Translating complex datasets into clear, actionable visualisations for non-technical audiences is essential.",
            "You will support A/B test evaluation, funnel analysis, and cohort studies for product and marketing teams.",
            "Responsibilities include building self-serve analytics dashboards and conducting ad-hoc analyses on demand.",
            "You will collaborate with data engineers to ensure pipelines feeding your analyses are reliable and well-documented.",
            "Experience with dbt for data modelling and transformation in a modern analytics stack is highly valued.",
            "You will track business KPIs, build executive reporting packs, and contribute to the weekly business review process.",
            "Conducting root-cause analyses and identifying growth opportunities from large datasets is a core expectation.",
        ],
        "salary_range": ["12,000–18,000 SAR/month", "16,000–24,000 SAR/month", "20,000–30,000 SAR/month"],
    },
    # ── Software Engineering / Backend ────────────────────────────────────────
    {
        "key": "software_engineering", "count": 140, "label": "Software Engineering",
        "titles": [
            "Backend Engineer", "Senior Backend Engineer", "Software Engineer",
            "Senior Software Engineer", "Full Stack Engineer",
            "API Engineer", "Platform Engineer", "Staff Engineer",
        ],
        "skills_pool": [
            "Python, FastAPI, PostgreSQL, Docker, Kubernetes, Git, REST API, AWS, Redis, SQL",
            "Python, Django, PostgreSQL, Docker, AWS, Git, REST API, Celery, Redis, SQL, Agile",
            "Java, Spring Boot, PostgreSQL, Docker, Kubernetes, Git, REST API, AWS, SQL, CI/CD",
            "Python, Flask, MongoDB, Docker, AWS, Git, REST API, SQL, Redis, GitHub",
            "TypeScript, Node.js, PostgreSQL, Docker, AWS, Git, REST API, React, SQL, CI/CD",
            "Python, FastAPI, MySQL, Redis, Docker, Kubernetes, AWS, GraphQL, Git, CI/CD",
            "Go, PostgreSQL, Docker, Kubernetes, AWS, Git, REST API, gRPC, SQL, CI/CD",
            "Python, Microservices, Kafka, PostgreSQL, Docker, Kubernetes, AWS, Git, SQL, CI/CD",
        ],
        "body_sentences": [
            "You will design and build RESTful APIs that power web and mobile products used by millions of users.",
            "Responsibilities include database schema design, query optimisation, and ensuring API performance at scale.",
            "You will write clean, testable code with thorough documentation and participate actively in peer code reviews.",
            "Contributing to system design discussions and defining API contracts with frontend and mobile teams is expected.",
            "You will build and maintain microservices, manage service-to-service communication, and handle distributed system complexity.",
            "Participation in Agile ceremonies, sprint planning, and continuous delivery is part of everyday engineering life here.",
            "You will own features end-to-end: from design and implementation through to monitoring in production.",
            "Collaboration with security teams to implement secure coding practices and conduct threat modelling is required.",
            "Building reliable, idempotent background jobs and event-driven workflows using Celery, Kafka, or SQS is expected.",
        ],
        "salary_range": ["15,000–22,000 SAR/month", "20,000–30,000 SAR/month", "28,000–42,000 SAR/month"],
    },
    # ── Data Engineering ──────────────────────────────────────────────────────
    {
        "key": "data_engineering", "count": 140, "label": "Data Engineering",
        "titles": [
            "Data Engineer", "Senior Data Engineer", "Analytics Engineer",
            "ETL Developer", "Data Platform Engineer", "Big Data Engineer",
            "Staff Data Engineer", "Data Infrastructure Engineer",
        ],
        "skills_pool": [
            "Python, Apache Spark, Airflow, SQL, dbt, AWS, Kafka, PostgreSQL, Docker, Git",
            "Python, ETL, Airflow, SQL, Redshift, dbt, Spark, Docker, AWS, Git",
            "Python, Kafka, Spark, Airflow, SQL, Azure, dbt, Docker, Git, CI/CD",
            "Python, dbt, Snowflake, Airflow, SQL, AWS, Spark, Docker, Git, ETL",
            "Python, Spark, Hadoop, Hive, Airflow, SQL, AWS, Docker, Kafka, Git",
            "Python, Databricks, Delta Lake, Spark, SQL, Azure, Airflow, dbt, Git, CI/CD",
            "Python, BigQuery, dbt, Airflow, SQL, Google Cloud, Docker, Kafka, Git, ETL",
            "Python, Flink, Kafka, Spark, SQL, AWS, Docker, Kubernetes, Git, CI/CD",
        ],
        "body_sentences": [
            "You will build and optimise data pipelines using Apache Airflow and Spark, processing terabytes of structured and unstructured data daily.",
            "Implementing data models with dbt, monitoring pipeline health, and ensuring SLA compliance are core responsibilities.",
            "You will work closely with data scientists to provide clean, well-documented feature datasets ready for model training.",
            "Architecting batch and real-time ETL pipelines, managing our data lake, and overseeing schema evolution are expected.",
            "You will champion data quality practices including automated testing, observability, and lineage tracking.",
            "Collaboration with analysts and scientists to understand data requirements and translate them into robust engineering solutions is central to the role.",
            "Building and maintaining a modern data stack (dbt + Airflow + Snowflake/BigQuery) is a key deliverable.",
            "You will manage our data warehouse infrastructure, optimise query performance, and reduce cloud costs.",
            "Designing and implementing real-time streaming pipelines using Kafka and Flink is highly valued.",
        ],
        "salary_range": ["18,000–26,000 SAR/month", "24,000–35,000 SAR/month", "30,000–45,000 SAR/month"],
    },
    # ── Product / Project Management ──────────────────────────────────────────
    {
        "key": "product_management", "count": 130, "label": "Product & Project Management",
        "titles": [
            "Product Manager", "Senior Product Manager", "Technical Product Manager",
            "AI Product Manager", "Data Product Manager", "Project Manager",
            "Agile Coach", "Program Manager",
        ],
        "skills_pool": [
            "Product Management, Agile, Scrum, SQL, Data Analysis, Communication, Leadership, Roadmapping, Python, Jira",
            "Product Management, Agile, SQL, Power BI, Communication, Critical Thinking, Project Management, Excel, Leadership",
            "Technical Product Management, Agile, SQL, REST API, Communication, Leadership, Data Analysis, Problem Solving",
            "AI Product Management, Machine Learning, SQL, Agile, Communication, Data Analysis, Leadership, Roadmapping",
            "Project Management, Agile, Scrum, SQL, Excel, Communication, Leadership, Critical Thinking, Risk Management",
            "Product Management, A/B Testing, SQL, Python, Data Analysis, Communication, Agile, Roadmapping, Jira",
        ],
        "body_sentences": [
            "You will define the product vision and roadmap, translate business requirements into engineering stories, and prioritise features ruthlessly.",
            "Working in Agile squads, you will partner with engineering, design, data science, and commercial teams to ship high-impact features.",
            "Strong analytical skills — including comfort with SQL and data dashboards — are essential to inform your decisions.",
            "You will own KPIs, run user interviews, and synthesise qualitative and quantitative feedback into actionable improvements.",
            "Communicating project status to executive stakeholders and managing risk proactively are critical aspects of the role.",
            "Experience working on ML or data-heavy products and ability to discuss technical trade-offs with engineers is a strong differentiator.",
            "Facilitating sprint ceremonies, managing the product backlog, and ensuring on-time delivery are daily responsibilities.",
            "You will define acceptance criteria, manage dependencies across teams, and drive resolution of blockers.",
            "Conducting competitive analysis, market research, and user research to inform product strategy is expected.",
        ],
        "salary_range": ["20,000–30,000 SAR/month", "28,000–40,000 SAR/month", "38,000–55,000 SAR/month"],
    },
    # ── Cybersecurity ─────────────────────────────────────────────────────────
    {
        "key": "cybersecurity", "count": 140, "label": "Cybersecurity",
        "titles": [
            "Cybersecurity Analyst", "Information Security Engineer", "SOC Analyst",
            "Penetration Tester", "Cloud Security Engineer",
            "Security Operations Engineer", "Threat Intelligence Analyst",
            "Application Security Engineer",
        ],
        "skills_pool": [
            "Cybersecurity, SIEM, Python, Linux, Network Security, Threat Analysis, SQL, Docker, AWS, Git",
            "Cybersecurity, Penetration Testing, Python, Linux, Kali Linux, Metasploit, SQL, Docker, Git",
            "Cybersecurity, Cloud Security, AWS, Azure, Python, Linux, Docker, Kubernetes, Git, CI/CD",
            "Cybersecurity, SOC, SIEM, Python, Linux, Threat Hunting, SQL, Network Security, Communication",
            "Cybersecurity, Application Security, Python, OWASP, Docker, Kubernetes, AWS, Git, CI/CD",
            "Cybersecurity, Threat Intelligence, Python, Linux, SIEM, SQL, Network Security, Git, Communication",
            "Cybersecurity, DevSecOps, Python, Docker, Kubernetes, AWS, Git, CI/CD, Linux, SAST",
        ],
        "body_sentences": [
            "You will monitor security events using SIEM tools, investigate alerts, and lead incident response activities.",
            "Conducting vulnerability assessments and coordinating remediation with engineering teams will be a regular part of your work.",
            "You will develop and maintain security policies aligned with NCA, ISO 27001, and SAMA cybersecurity frameworks.",
            "Proficiency in Python scripting for automation of security tasks and familiarity with cloud security posture management are valued.",
            "You will perform penetration tests on web applications, APIs, and internal network infrastructure and produce detailed reports.",
            "Threat modelling, red team exercises, and security code reviews are core activities in this role.",
            "Close collaboration with DevOps to embed security into CI/CD pipelines (DevSecOps) is expected.",
            "You will track threat intelligence feeds, analyse IOCs, and proactively hunt for threats in the environment.",
            "Reviewing application code for security vulnerabilities (OWASP Top 10) and advising developers on secure coding is required.",
        ],
        "salary_range": ["16,000–24,000 SAR/month", "22,000–32,000 SAR/month", "28,000–42,000 SAR/month"],
    },
]


def _generate_dummy_jobs(total: int = 1000) -> List[Dict]:
    """
    Generate `total` realistic Saudi tech job listings distributed across
    seven sectors. Uses deterministic seed for reproducibility.
    """
    random.seed(42)
    jobs: List[Dict] = []

    opening_cy = cycle(_OPENING)
    closing_cy = cycle(_CLOSING)

    for sector in _SECTORS:
        body_cy = cycle(sector["body_sentences"])
        skills_cy = cycle(sector["skills_pool"])

        for _ in range(sector["count"]):
            title = random.choice(sector["titles"])
            company = random.choice(_COMPANIES)
            location = random.choice(_LOCATIONS)
            # Required years must align with title seniority, otherwise the
            # dataset has "Senior Engineer, 1 year required" nonsense that
            # breaks the seniority filter and confuses users.
            title_l = title.lower()
            if any(k in title_l for k in ("director", "head of", "chief", "vp ", "vice president")):
                exp_years = random.randint(8, 12)
            elif any(k in title_l for k in ("senior", "lead", "staff", "principal", "manager")):
                exp_years = random.randint(5, 9)
            elif any(k in title_l for k in ("junior", "associate", "entry", "intern", "graduate", "trainee")):
                exp_years = random.randint(0, 2)
            else:
                exp_years = random.randint(2, 5)
            education = random.choice(_EDUCATION)
            salary = random.choice(sector["salary_range"])
            skills = next(skills_cy)

            # Build a 4–6 sentence description
            opening = next(opening_cy).format(
                title=title, company=company, location=location,
                sector_label=sector["label"],
            )
            body = " ".join(
                next(body_cy) for _ in range(random.randint(3, 5))
            )
            closing = next(closing_cy).format(
                education=education, exp=exp_years,
            )
            description = f"{opening} {body} {closing}"

            jobs.append({
                "job_title": title,
                "company": company,
                "location": location,
                "description": description,
                "required_skills": skills,
                "experience_years": exp_years,
                "education": education,
                "salary_range": salary,
            })

    random.shuffle(jobs)
    return jobs[:total]


# ══════════════════════════════════════════════════════════════════════════════
# BAYT SCRAPER
# ══════════════════════════════════════════════════════════════════════════════

def _scrape_bayt(max_pages: int = 3) -> List[Dict]:
    """Attempt to scrape Saudi listings from Bayt.com. Raises RuntimeError on failure."""
    if BeautifulSoup is None:
        raise RuntimeError("beautifulsoup4 is not installed.")

    jobs: List[Dict] = []
    base_url = "https://www.bayt.com/en/saudi-arabia/jobs/"

    for page in range(1, max_pages + 1):
        resp = requests.get(f"{base_url}?page={page}", headers=_HEADERS, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("li[class*='has-pointer-d']")
        if not cards:
            break

        for card in cards:
            title_el = card.select_one("h2.jb-title, [data-automation-id='job-title']")
            company_el = card.select_one("[data-automation-id='job-company']")
            location_el = card.select_one("[data-automation-id='job-location']")
            desc_el = card.select_one(".jb-description, p")
            jobs.append({
                "job_title": title_el.get_text(strip=True) if title_el else "",
                "company": company_el.get_text(strip=True) if company_el else "",
                "location": location_el.get_text(strip=True) if location_el else "Saudi Arabia",
                "description": desc_el.get_text(strip=True) if desc_el else "",
                "required_skills": "",
                "experience_years": "",
                "education": "",
                "salary_range": "",
            })

        time.sleep(random.uniform(2.0, 4.0))

    return jobs


# ══════════════════════════════════════════════════════════════════════════════
# JADARAT INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════

def run_jadarat_collector() -> List[Dict]:
    """
    Attempt to collect jobs from Jadarat.sa using Playwright.
    Returns list of job dicts, or [] if unavailable.
    """
    try:
        from jadarat_collector import run_jadarat_collector as _run
        results = _run()
        return results
    except Exception as exc:
        print(f"  Jadarat collector error: {exc}")
        return []


def run_linkedin_collector() -> List[Dict]:
    """
    Attempt to collect jobs from LinkedIn via python-jobspy.
    Returns list of job dicts, or [] if unavailable.
    """
    try:
        from linkedin_collector import run_linkedin_collector as _run
        return _run()
    except Exception as exc:
        print(f"  LinkedIn collector error: {exc}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# CLEAN + SAVE
# ══════════════════════════════════════════════════════════════════════════════

def _clean_jobs(jobs: List[Dict]) -> List[Dict]:
    """Strip whitespace and drop rows with empty job_title."""
    return [
        {k: str(v).strip() for k, v in job.items()}
        for job in jobs
        if str(job.get("job_title", "")).strip()
    ]


def _save_csv(jobs: List[Dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(jobs)


def _invalidate_embedding_cache() -> None:
    """
    Remove ChromaDB content-hash sidecar and cluster cache so model.py
    rebuilds embeddings + clusters against the new dataset on next access.
    """
    hash_file = Path("data/chromadb/index_hash.txt")
    if hash_file.exists():
        hash_file.unlink()
    cluster_cache = Path("data/cluster_cache.pkl")
    if cluster_cache.exists():
        cluster_cache.unlink()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def collect_jobs(use_dummy_on_fail: bool = True) -> List[Dict]:
    """
    Collect Saudi job listings.
    Order: Jadarat.sa (Playwright) → LinkedIn (python-jobspy) →
           Bayt.com → 1000-job synthetic dataset (FALLBACK ONLY).
    Saves raw and processed CSVs, invalidates embedding cache.
    """
    jobs: List[Dict] = []

    # ── 1. Try Jadarat ────────────────────────────────────────────────────────
    print("Attempting Jadarat.sa collection (Playwright)...")
    jadarat_jobs = run_jadarat_collector()
    if jadarat_jobs:
        print(f"  Jadarat: collected {len(jadarat_jobs)} jobs.")
        jobs.extend(jadarat_jobs)
    else:
        print("  Jadarat: unavailable or returned no results.")

    # ── 2. Try LinkedIn (python-jobspy) ───────────────────────────────────────
    if not jobs:
        print("Attempting LinkedIn collection (python-jobspy)...")
        linkedin_jobs = run_linkedin_collector()
        if linkedin_jobs:
            print(f"  LinkedIn: collected {len(linkedin_jobs)} jobs.")
            jobs.extend(linkedin_jobs)
        else:
            print("  LinkedIn: unavailable or returned no results.")

    # ── 3. Try Bayt.com ───────────────────────────────────────────────────────
    if not jobs:
        print("Attempting Bayt.com scraping...")
        try:
            bayt_jobs = _scrape_bayt()
            if bayt_jobs:
                print(f"  Bayt.com: scraped {len(bayt_jobs)} jobs.")
                jobs.extend(bayt_jobs)
        except Exception as exc:
            print(f"  Bayt.com failed: {exc}")

    # ── 4. Fall back to synthetic data (FALLBACK — NOT REAL) ──────────────────
    if not jobs and use_dummy_on_fail:
        print("WARNING: All real sources failed. Using synthetic fallback dataset.")
        jobs = _generate_dummy_jobs(1000)
        print(f"  Generated {len(jobs)} synthetic jobs (fallback only).")

    # ── Save ──────────────────────────────────────────────────────────────────
    _save_csv(jobs, RAW_PATH)
    print(f"Raw data saved to {RAW_PATH} ({len(jobs)} rows)")

    clean = _clean_jobs(jobs)
    _save_csv(clean, CLEAN_PATH)
    print(f"Clean data saved to {CLEAN_PATH} ({len(clean)} rows)")

    _invalidate_embedding_cache()
    print("Embedding cache cleared.")

    return clean


if __name__ == "__main__":
    collect_jobs()
