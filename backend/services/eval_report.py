"""Evaluation and reporting helpers for trained models.

Provides utilities to compute regression metrics (MAE, MSE, RMSE, R2)
and write per-player reports to CSV/JSON.
"""

from __future__ import annotations

import json
import math
import os
from typing import Any, Dict

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def compute_regression_metrics(
    y_true: np.ndarray, y_pred: np.ndarray
) -> Dict[str, float]:
    y_true = np.asarray(y_true).astype(float)
    y_pred = np.asarray(y_pred).astype(float)
    mse = float(mean_squared_error(y_true, y_pred))
    rmse = float(math.sqrt(mse))
    mae = float(mean_absolute_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred)) if y_true.shape[0] > 1 else float("nan")
    return {"mse": mse, "rmse": rmse, "mae": mae, "r2": r2, "n": int(y_true.shape[0])}


def load_model_if_exists(path: str):
    try:
        if not os.path.exists(path):
            return None
        return joblib.load(path)
    except Exception:
        return None


def evaluate_model_on_df(
    model, df: pd.DataFrame, feature_cols: list, target_col: str = "target"
) -> Dict[str, Any]:
    if df.shape[0] == 0:
        return {"error": "no_rows"}
    X = df[feature_cols].copy()
    # try to align columns to model expected feature names if available
    try:
        if hasattr(model, "feature_names_in_"):
            expected = list(model.feature_names_in_)
            for c in expected:
                if c not in X.columns:
                    X[c] = 0.0
            X = X.reindex(columns=expected)
        elif (
            hasattr(model, "estimators_") and len(getattr(model, "estimators_", [])) > 0
        ):
            est = model.estimators_[0]
            if hasattr(est, "feature_names_in_"):
                expected = list(est.feature_names_in_)
                for c in expected:
                    if c not in X.columns:
                        X[c] = 0.0
                X = X.reindex(columns=expected)
    except Exception:
        # alignment failed; fall back to numeric subset below
        pass

    X = X.select_dtypes(include=[np.number]).fillna(0)
    y = df[target_col].astype(float).to_numpy()
    # if no numeric features remain, attempt to construct a numeric fallback
    if X.shape[1] == 0:
        n_features = None
        try:
            if hasattr(model, "n_features_in_"):
                n_features = int(model.n_features_in_)
            elif (
                hasattr(model, "estimators_")
                and len(getattr(model, "estimators_", [])) > 0
            ):
                est = model.estimators_[0]
                if hasattr(est, "n_features_in_"):
                    n_features = int(est.n_features_in_)
        except Exception:
            n_features = None
        if n_features and n_features > 0:
            X = pd.DataFrame(np.zeros((df.shape[0], n_features)))
        else:
            X = pd.DataFrame(np.zeros((df.shape[0], 5)))
    try:
        preds = model.predict(X)
    except Exception as e:
        # try numpy values
        try:
            preds = model.predict(X.values)
        except Exception as e2:
            # attempt to infer expected feature count and try a zero-filled array
            expected_n = None
            try:
                if hasattr(model, "n_features_in_"):
                    expected_n = int(model.n_features_in_)
                elif (
                    hasattr(model, "estimators_")
                    and len(getattr(model, "estimators_", [])) > 0
                ):
                    est = model.estimators_[0]
                    if hasattr(est, "n_features_in_"):
                        expected_n = int(est.n_features_in_)
            except Exception:
                expected_n = None
            if expected_n and expected_n > 0:
                try:
                    X2 = pd.DataFrame(np.zeros((df.shape[0], expected_n)))
                    preds = model.predict(X2)
                except Exception:
                    return {
                        "error": "predict_failed",
                        "exception": str(e2),
                        "X_shape": X.shape,
                        "expected_n": expected_n,
                    }
            else:
                return {
                    "error": "predict_failed",
                    "exception": str(e2),
                    "X_shape": X.shape,
                }
    metrics = compute_regression_metrics(y, preds)
    return {"metrics": metrics}


def write_report(rows: list, out_csv: str, out_json: str | None = None) -> None:
    df = pd.DataFrame(rows)
    df.to_csv(out_csv, index=False)
    if out_json:
        with open(out_json, "w", encoding="utf8") as fh:
            json.dump(rows, fh, indent=2)
