#!/usr/bin/env python3
"""Optuna tuning scaffold for RandomForest hyperparameters.

This is a lightweight script intended for local/CI use. Optuna is optional;
the script will bail with a friendly message if `optuna` is not installed.
"""
from __future__ import annotations

import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    try:
        import optuna
    except Exception:
        logger.error(
            "Optuna is not installed. Install with `pip install optuna` to use this script."
        )
        sys.exit(1)

    import numpy as np
    import pandas as pd
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import cross_val_score

    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True, help="CSV with features + target column")
    p.add_argument("--target", default="target")
    p.add_argument("--trials", type=int, default=20)
    args = p.parse_args()

    df = pd.read_csv(args.csv)
    if args.target not in df.columns:
        logger.error("Target column %s not found in CSV", args.target)
        sys.exit(2)

    X = df.drop(columns=[args.target]).select_dtypes(include=[float, int]).fillna(0)
    y = df[args.target].values

    def objective(trial: "optuna.Trial"):
        n_estimators = trial.suggest_int("n_estimators", 50, 300)
        max_depth = trial.suggest_int("max_depth", 3, 16)
        min_samples_leaf = trial.suggest_int("min_samples_leaf", 1, 10)
        model = RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_leaf=min_samples_leaf,
            random_state=42,
        )
        # negative MSE -> lower is better, so return RMSE
        scores = cross_val_score(model, X, y, scoring="neg_mean_squared_error", cv=3)
        rmse = float(np.sqrt(-scores.mean()))
        return rmse

    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=args.trials)

    logger.info("Best trial: %s", study.best_trial.params)
    print(study.best_trial.params)


if __name__ == "__main__":
    main()
