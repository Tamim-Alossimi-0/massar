// Sample CV used by the "Try Demo" button so visitors can test the
// matching pipeline without needing a real resume. Written in plain
// text so /api/skills/extract treats it as a .txt upload with no
// server-side parsing surprises.

export const DEMO_CV_FILENAME = "demo-data-scientist.txt"

export const DEMO_CV_TEXT = `Sarah Al-Qahtani
Data Scientist | Riyadh, Saudi Arabia
sarah.alqahtani@example.com | +966 5XX XXX XXX
linkedin.com/in/sarah-alqahtani | github.com/sarahaq

SUMMARY
Data Scientist with 4 years of experience building production machine
learning systems for SaaS and retail companies in the Kingdom. Strong
Python and SQL foundation, fluent in both statistical modeling and
deep learning, comfortable owning a project from data collection to
dashboard. Known for clear communication with non-technical stakeholders.

TECHNICAL SKILLS
- Languages: Python, R, SQL, Bash
- Machine Learning / AI: scikit-learn, XGBoost, LightGBM, TensorFlow,
  PyTorch, Keras, NLP, transformers, BERT, time series, forecasting,
  feature engineering, A/B testing, model deployment
- Data Engineering: Pandas, NumPy, SciPy, Spark, PySpark, Airflow,
  dbt, ETL pipelines, BigQuery, PostgreSQL, MongoDB, Redshift
- Visualization / BI: Matplotlib, Seaborn, Plotly, Tableau, Power BI
- Cloud / DevOps: AWS (S3, SageMaker, Lambda), Docker, Kubernetes,
  Git, GitHub Actions, CI/CD, Linux
- Statistics: hypothesis testing, regression, clustering, causal
  inference, Bayesian methods
- Soft: communication, problem solving, leadership, agile, scrum

EXPERIENCE

Senior Data Scientist — Jahez (Riyadh)                   2022 – Present
- Built a demand-forecasting model (XGBoost + Prophet ensemble) that
  reduced delivery ETA error by 18% across 12 cities.
- Led the NLP pipeline for customer-support ticket triage using
  transformers and BERT, deployed on AWS SageMaker behind a FastAPI
  microservice. P95 latency 140 ms, 2M inferences/day.
- Mentored 3 junior analysts; ran a weekly stats clinic on A/B testing
  and experiment design for the product team.
- Partnered with data engineering to migrate the offline training
  stack from cron + Python scripts to Airflow + dbt on BigQuery.

Data Analyst — STC Pay (Riyadh)                          2020 – 2022
- Designed and shipped fraud-detection features on top of Spark jobs,
  lowering the false-positive rate by 25% while keeping recall flat.
- Authored 40+ SQL dashboards in Power BI covering payment flows,
  customer churn, cohort LTV, and funnel conversion. Adopted by the
  CX, Growth, and Finance teams as their single source of truth.
- Partnered with product managers on the weekly experimentation
  roadmap, reviewing test designs and post-mortems.

Junior Analyst (intern) — Saudi Aramco Digital           2019 – 2020
- Prototyped a time-series anomaly detector for pipeline sensor
  streams using Python, Pandas, and scikit-learn.
- Built an interactive Plotly dashboard used by the reliability
  engineering team for root-cause investigations.

EDUCATION
BSc Computer Science — King Saud University              2016 – 2020
GPA 3.8 / 4.0.  Relevant coursework: machine learning, databases,
statistics, linear algebra, data structures, operating systems.

PROJECTS
Riyadh Real Estate Price Estimator
- Scraped 50k listings with Playwright, trained a LightGBM regressor
  (RMSE 42K SAR), deployed as a Streamlit app.

COVID-19 Dashboard for Saudi Arabia
- Public Plotly / Dash app on top of MOH open data, 10k+ monthly
  page views in 2021. Infra on AWS Lambda + S3 static hosting.

CERTIFICATIONS
- AWS Certified Machine Learning — Specialty (2023)
- Google Cloud Professional Data Engineer (2022)
`
