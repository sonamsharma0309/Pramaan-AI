"""Appeal win-probability model.

Starts as a logistic regression trained on SYNTHETIC rule-informed data (no public outcome dataset exists).
`scripts/train_predictor.py` retrains it from real recorded outcomes once >= MIN_OUTCOMES exist and saves
data/predictor.json, which is then loaded automatically. Every prediction reports `model_kind`
("synthetic" or "trained") so the UI can label estimates honestly.
"""
import json
import math
from datetime import date, datetime

import numpy as np

from .. import config

FEATURES = ["denial_prior", "evidence_coverage", "policy_match", "has_clinical_notes", "claim_age", "amount_size"]
NICE = {"denial_prior": "Denial type history", "evidence_coverage": "Evidence coverage of policy criteria", "policy_match": "Payer policy match",
        "has_clinical_notes": "Clinical notes attached", "claim_age": "Time since denial", "amount_size": "Claim size"}
MIN_OUTCOMES = 50
MODEL_PATH = config.DATA_DIR / "predictor.json"
_model: dict | None = None


def _synthetic(n: int = 4000, seed: int = 7):
    rng = np.random.default_rng(seed)
    prior, cov, pol = rng.uniform(0.05, 0.85, n), rng.beta(2, 2, n), rng.beta(2.5, 2, n)
    notes, age, amt = (rng.random(n) > 0.12).astype(float), rng.uniform(0, 1, n), rng.uniform(0, 1, n)
    cov, pol = cov * notes, pol * (0.4 + 0.6 * notes)
    z = -3.9 + 2.6 * prior + 3.2 * cov + 1.6 * pol + 0.4 * notes - 1.3 * age - 0.25 * amt + rng.normal(0, 0.45, n)
    y = (rng.random(n) < 1 / (1 + np.exp(-z))).astype(int)
    return np.column_stack([prior, cov, pol, notes, age, amt]), y


def fit(X, y) -> dict:
    from sklearn.linear_model import LogisticRegression
    m = LogisticRegression(max_iter=1000).fit(X, y)
    return {"coef": m.coef_[0].tolist(), "intercept": float(m.intercept_[0]), "n": int(len(y))}


def get_model() -> dict:
    global _model
    if _model is None:
        if MODEL_PATH.exists():
            try:
                _model = json.loads(MODEL_PATH.read_text())
            except (OSError, ValueError):
                _model = None
        if _model is None:
            X, y = _synthetic()
            _model = {**fit(X, y), "kind": "synthetic"}
    return _model


def reset_model() -> None:
    global _model
    _model = None


def save_trained(X, y) -> dict:
    model = {**fit(np.asarray(X), np.asarray(y)), "kind": "trained"}
    MODEL_PATH.write_text(json.dumps(model))
    reset_model()
    return model


def days_since(d: str) -> int:
    try:
        return max(0, (date.today() - datetime.strptime(d[:10], "%Y-%m-%d").date()).days)
    except (ValueError, TypeError):
        return 30


def features(denial_prior: float, coverage: float, policy_match: float, has_notes: bool, denied_on: str, amount: float) -> list[float]:
    age = min(days_since(denied_on) / 180.0, 1.0)
    amt = min(math.log10(max(amount, 1)) / 5.0, 1.0)
    return [denial_prior, coverage, policy_match, 1.0 if has_notes else 0.0, age, amt]


def predict(denial_prior: float, coverage: float, policy_match: float, has_notes: bool, denied_on: str, amount: float) -> dict:
    m = get_model()
    x = np.array(features(denial_prior, coverage, policy_match, has_notes, denied_on, amount))
    coef = np.array(m["coef"])
    p = float(1 / (1 + math.exp(-(float(coef @ x) + m["intercept"]))))
    base = np.array([0.4, 0.5, 0.5, 1.0, 0.3, 0.5])
    contrib = (x - base) * coef
    factors = sorted([{"name": NICE[f], "impact": round(float(c), 2)} for f, c in zip(FEATURES, contrib, strict=True)], key=lambda d: -abs(d["impact"]))
    kind = m.get("kind", "synthetic")
    return {"probability": round(p, 3), "factors": factors, "days_since_denial": days_since(denied_on), "features": x.tolist(),
            "model_kind": kind, "model": f"LogisticRegression ({kind}, n={m.get('n', 0)})"}
