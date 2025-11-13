"""Training pipeline skeleton for player models.

This module provides utilities to train a per-player ensemble model.
It's intentionally small: it focuses on a tidy training function and
safe imports so the rest of the app can import this file even if
XGBoost is not available in the environment.
"""
from __future__ import annotations
from typing import Optional
import os
import logging

import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestRegressor, VotingRegressor
from sklearn.linear_model import ElasticNet

try:
    from xgboost import XGBRegressor  # type: ignore
    _HAS_XGB = True
except Exception:
    XGBRegressor = None  # type: ignore
    _HAS_XGB = False

import joblib

logger = logging.getLogger(__name__)


def _build_ensemble() -> VotingRegressor:
    estimators = []
    rf = RandomForestRegressor(n_estimators=100, random_state=42)
    estimators.append(("rf", rf))

    if _HAS_XGB and XGBRegressor is not None:
        xgb = XGBRegressor(n_estimators=100, random_state=42)
        estimators.append(("xgb", xgb))

    elastic = ElasticNet(alpha=0.1, l1_ratio=0.5, random_state=42)
    estimators.append(("elastic", elastic))

    # Weights favour tree-based models when available
    weights = [0.45, 0.45, 0.1] if _HAS_XGB else [0.6, 0.4]
    # Adjust weights length to match estimators
    weights = weights[: len(estimators)]

    ensemble = VotingRegressor(estimators=estimators, weights=weights)
    return ensemble


def train_player_model(df: pd.DataFrame, target_col: str = "target") -> VotingRegressor:
    """Train an ensemble model from a feature DataFrame.

    df: DataFrame containing features and the `target_col`.
    Returns a fitted VotingRegressor.
    """
    if target_col not in df.columns:
        raise ValueError(f"target_col '{target_col}' not in DataFrame")

    X = df.drop(columns=[target_col])
    y = df[target_col]

    # Replace non-numeric values and infs
    X = X.select_dtypes(include=[np.number]).fillna(0)

    model = _build_ensemble()
    model.fit(X, y)

    logger.info("Trained model on %d rows, %d features", X.shape[0], X.shape[1])
    return model


def save_model(model, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(model, path)


def load_model(path: str):
    if not os.path.exists(path):
        return None
    return joblib.load(path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train a player model from CSV")
    parser.add_argument("--csv", required=True, help="CSV file with features + target column")
    parser.add_argument("--target", default="target", help="Name of the target column")
    parser.add_argument("--out", required=True, help="Output path for the model .pkl")
    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    model = train_player_model(df, target_col=args.target)
    save_model(model, args.out)
    print("Saved model to:", args.out)
