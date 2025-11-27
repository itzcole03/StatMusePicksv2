"""Run a small Optuna XGBoost hyperparameter tuning job on synthetic data.

Saves best params to `backend/models_store/tune_reports/xgb_best.json`.
"""

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

repo_root = Path(__file__).resolve().parents[1]
out_dir = repo_root / "backend" / "models_store" / "tune_reports"
os.makedirs(out_dir, exist_ok=True)

from backend.services.training_pipeline import tune_xgboost_hyperparams


def make_synthetic(n=200, features=8):
    rng = np.random.RandomState(0)
    X = rng.randn(n, features)
    coef = rng.randn(features)
    y = X.dot(coef) + rng.normal(scale=0.5, size=n)
    cols = [f"f{i}" for i in range(features)]
    df = pd.DataFrame(X, columns=cols)
    df["target"] = y
    return df


def main():
    df = make_synthetic(300, features=10)
    try:
        best = tune_xgboost_hyperparams(df, target_col="target", n_trials=20)
    except RuntimeError as e:
        print("Tuning failed:", e)
        return 2
    out = out_dir / "xgb_best.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(best, fh, indent=2)
    print("Wrote best params to", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
