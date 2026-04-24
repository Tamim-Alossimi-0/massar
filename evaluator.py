"""
evaluator.py — Evaluate Sentence Transformers matching quality on 10 labeled pairs.
Run with: python evaluator.py
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from sklearn.metrics.pairwise import cosine_similarity

from model import embed_texts

# ── 10 labeled test pairs ────────────────────────────────────────────────────
# (cv_snippet, job_description, expected_match: True=relevant, False=irrelevant)
TEST_PAIRS: List[Tuple[str, str, bool]] = [
    (
        "5 years Python, Machine Learning, SQL, TensorFlow, data pipelines, NLP",
        "Data Scientist needed with Python, ML, NLP experience. Saudi Aramco.",
        True,
    ),
    (
        "5 years Python, Machine Learning, SQL, TensorFlow, data pipelines, NLP",
        "Civil Engineer with AutoCAD, structural design, 8 years experience.",
        False,
    ),
    (
        "Financial analyst, Excel, Power BI, risk management, 4 years banking",
        "Financial Analyst at Riyad Bank. Excel, Power BI, SAP required.",
        True,
    ),
    (
        "Financial analyst, Excel, Power BI, risk management, 4 years banking",
        "Backend Developer with Node.js, Docker, Kubernetes.",
        False,
    ),
    (
        "Mechanical engineer, AutoCAD, MATLAB, project management, 6 years",
        "Project Engineer at SABIC. AutoCAD, MATLAB, Agile required.",
        True,
    ),
    (
        "Mechanical engineer, AutoCAD, MATLAB, project management, 6 years",
        "Clinical Data Analyst, Excel, medical coding, hospital setting.",
        False,
    ),
    (
        "DevOps engineer, Docker, Kubernetes, AWS, CI/CD, Linux, 3 years",
        "DevOps Engineer at STC. Docker, Kubernetes, AWS essential.",
        True,
    ),
    (
        "DevOps engineer, Docker, Kubernetes, AWS, CI/CD, Linux, 3 years",
        "Pharmacist, hospital management, Arabic, communication skills.",
        False,
    ),
    (
        "BI Developer, Power BI, Tableau, SQL, data visualization, 5 years",
        "BI Developer at Mobily. Power BI, Tableau, SQL required.",
        True,
    ),
    (
        "BI Developer, Power BI, Tableau, SQL, data visualization, 5 years",
        "Risk Manager, financial analysis, SAP, Arabic, compliance.",
        False,
    ),
]

THRESHOLD = 0.25


def _st_scores(pairs: List[Tuple[str, str, bool]]) -> List[float]:
    """Compute Sentence Transformer cosine similarity for each pair."""
    scores = []
    for cv, job, _ in pairs:
        embs = embed_texts([cv, job])
        score = float(cosine_similarity(embs[0].reshape(1, -1), embs[1:2])[0, 0])
        scores.append(score)
    return scores


def _evaluate(scores: List[float], labels: List[bool],
              threshold: float) -> Tuple[float, float]:
    """Return (precision, accuracy) for given scores and ground-truth labels."""
    preds = [s >= threshold for s in scores]
    tp = sum(p and l for p, l in zip(preds, labels))
    fp = sum(p and not l for p, l in zip(preds, labels))
    correct = sum(p == l for p, l in zip(preds, labels))
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    return round(precision, 3), round(correct / len(labels), 3)


def run_evaluation() -> None:
    labels = [pair[2] for pair in TEST_PAIRS]

    print("Running Sentence Transformer evaluation...")
    scores = _st_scores(TEST_PAIRS)
    precision, accuracy = _evaluate(scores, labels, THRESHOLD)

    sep = "-" * 45
    print(f"\n{sep}")
    print(f"{'Model':<30} {'Precision':>7} {'Accuracy':>7}")
    print(sep)
    print(f"{'Sentence Transformers (MiniLM)':<30} {precision:>7.3f} {accuracy:>7.3f}")
    print(sep)

    print("\nPer-pair details:")
    for i, (cv, job, expected) in enumerate(TEST_PAIRS):
        pred = scores[i] >= THRESHOLD
        status = "OK" if pred == expected else "WRONG"
        print(f"  [{status}] Pair {i+1:2d}  expected={'YES' if expected else 'NO ':3s}"
              f"  score={scores[i]:.3f}  cv='{cv[:45]}...'")


if __name__ == "__main__":
    run_evaluation()
