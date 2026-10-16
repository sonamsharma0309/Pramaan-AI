"""Retrain the win-probability model from REAL recorded appeal outcomes.

Needs at least MIN_OUTCOMES (50) decided appeals (won / partial / lost). Otherwise the synthetic model is kept.
Usage: python scripts/train_predictor.py [--force]   (--force trains with fewer rows, for experiments only)
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import database as db  # noqa: E402
from backend.services import predictor  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    db.init_db()
    X, y = [], []
    for r in db.q("SELECT analysis, outcome FROM appeals WHERE outcome IN ('won','partial','lost')"):
        feats = (json.loads(r["analysis"] or "{}").get("prediction") or {}).get("features")
        if feats and len(feats) == len(predictor.FEATURES):
            X.append(feats)
            y.append(1 if r["outcome"] in ("won", "partial") else 0)
    print(f"Found {len(y)} decided appeals ({sum(y)} positive).")
    if len(y) < predictor.MIN_OUTCOMES and not args.force:
        print(f"Need at least {predictor.MIN_OUTCOMES}. Keeping the synthetic model.")
        return 0
    if len(set(y)) < 2:
        print("All outcomes are the same class; cannot train yet. Keeping the current model.")
        return 0
    model = predictor.save_trained(X, y)
    print(f"Trained on {model['n']} outcomes and saved to {predictor.MODEL_PATH}. Restart the app to load it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
