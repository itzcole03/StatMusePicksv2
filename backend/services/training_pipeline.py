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
from sklearn.linear_model import Ridge

try:
    from backend.services.xgboost_wrapper import XGBoostWrapper
    _HAS_XGB = getattr(XGBoostWrapper, 'available', False)
except Exception:
    XGBoostWrapper = None
    _HAS_XGB = False

try:
    # StackingEnsemble implemented in backend.models.ensemble_model
    from backend.models.ensemble_model import StackingEnsemble
    _HAS_STACKING = True
except Exception:
    StackingEnsemble = None
    _HAS_STACKING = False

import joblib

logger = logging.getLogger(__name__)


def _build_ensemble() -> VotingRegressor:
    estimators = []
    rf = RandomForestRegressor(n_estimators=100, random_state=42)
    estimators.append(("rf", rf))

    if _HAS_XGB and XGBoostWrapper is not None:
        # Prefer constructing the real XGBRegressor (if xgboost module is available
        # via the wrapper) so VotingRegressor recognizes it as a regressor.
        try:
            xgb_mod = getattr(XGBoostWrapper, '__module__', None)
        except Exception:
            xgb_mod = None
        # fallback: try to access the xgboost module imported by the wrapper
        try:
            from backend.services import xgboost_wrapper as _xwb
            if getattr(_xwb, 'xgb', None) is not None:
                xgb_cls = _xwb.xgb.XGBRegressor
                xgb = xgb_cls(n_estimators=100, random_state=42)
                estimators.append(("xgb", xgb))
        except Exception:
            # if anything goes wrong, skip XGBoost estimator
            pass

    elastic = ElasticNet(alpha=0.1, l1_ratio=0.5, random_state=42)
    estimators.append(("elastic", elastic))

    # Weights favour tree-based models when available
    weights = [0.45, 0.45, 0.1] if _HAS_XGB else [0.6, 0.4]
    # Adjust weights length to match estimators
    weights = weights[: len(estimators)]

    ensemble = VotingRegressor(estimators=estimators, weights=weights)
    return ensemble


def train_player_model(df: pd.DataFrame, target_col: str = "target", use_stacking: bool = False) -> object:
    """Train an ensemble model from a feature DataFrame.

    df: DataFrame containing features and the `target_col`.
    If `use_stacking` and the stacking implementation is available, returns
    a fitted `StackingEnsemble`. Otherwise returns a fitted `VotingRegressor`.
    """
    if target_col not in df.columns:
        raise ValueError(f"target_col '{target_col}' not in DataFrame")

    X = df.drop(columns=[target_col])
    y = df[target_col]

    # Replace non-numeric values and infs
    X = X.select_dtypes(include=[np.number]).fillna(0)

    # Ensure multi-season feature columns exist so downstream models
    # reliably receive these engineered fields when present in context.
    MULTI_FEATURES = [
        'multi_PER',
        'multi_TS_PCT',
        'multi_BPM',
        'multi_USG_PCT',
        'multi_season_PTS_avg',
        'multi_season_count',
        'multi_PIE',
        'multi_off_rating',
        'multi_def_rating',
    ]

    for col in MULTI_FEATURES:
        if col not in df.columns:
            df[col] = 0.0

    X = df.drop(columns=[target_col])

    # Replace non-numeric values and infs; ensure multi features are numeric
    for col in MULTI_FEATURES:
        try:
            X[col] = X[col].astype(float)
        except Exception:
            X[col] = pd.to_numeric(X[col], errors='coerce').fillna(0.0)

    X = X.select_dtypes(include=[np.number]).fillna(0)

    # Optionally build and train a stacking ensemble
    if use_stacking and _HAS_STACKING and StackingEnsemble is not None:
        from sklearn.ensemble import GradientBoostingRegressor

        # build base learners
        rf = RandomForestRegressor(n_estimators=100, random_state=42)
        if _HAS_XGB and XGBoostWrapper is not None:
            try:
                from backend.services import xgboost_wrapper as _xwb
                if getattr(_xwb, 'xgb', None) is not None:
                    xgb_cls = _xwb.xgb.XGBRegressor
                    xgb_est = xgb_cls(n_estimators=100, random_state=42)
                else:
                    xgb_est = GradientBoostingRegressor(n_estimators=100, random_state=42)
            except Exception:
                xgb_est = GradientBoostingRegressor(n_estimators=100, random_state=42)
        else:
            xgb_est = GradientBoostingRegressor(n_estimators=100, random_state=42)

        enet = ElasticNet(alpha=0.1, l1_ratio=0.5, random_state=42)
        base_models = [("rf", rf), ("xg", xgb_est), ("en", enet)]
        stacking = StackingEnsemble(base_models=base_models, meta_model=Ridge(alpha=1.0), n_folds=5)
        stacking.train(X, y)
        logger.info("Trained StackingEnsemble on %d rows, %d features", X.shape[0], X.shape[1])
        return stacking

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
    parser.add_argument("--out", help="Output path for the model .pkl (defaults to backend/models_store/<csv_basename>.pkl)")
    parser.add_argument("--use-stacking", action="store_true", help="Train a StackingEnsemble instead of the VotingRegressor when available")
    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    model = train_player_model(df, target_col=args.target, use_stacking=bool(args.use_stacking))

    out_path = args.out
    if out_path is None:
        base = os.path.splitext(os.path.basename(args.csv))[0]
        suf = "_stacking" if args.use_stacking else ""
        out_dir = os.path.join("backend", "models_store")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{base}{suf}.pkl")

    save_model(model, out_path)
    print("Saved model to:", out_path)


def tune_random_forest_hyperparams(df: pd.DataFrame, target_col: str = "target", n_trials: int = 20) -> dict:
    """Run a small Optuna study to tune RandomForest hyperparameters.

    Returns the best parameters dict. Optuna is optional — if not installed
    a RuntimeError is raised with an instruction to install it.
    """
    try:
        import optuna
    except Exception:
        raise RuntimeError("Optuna not installed. Install with `pip install optuna` to enable tuning")

    if target_col not in df.columns:
        raise ValueError(f"target_col '{target_col}' not in DataFrame")

    X = df.drop(columns=[target_col]).select_dtypes(include=[np.number]).fillna(0)
    y = df[target_col].astype(float).values

    def objective(trial: 'optuna.Trial'):
        n_estimators = trial.suggest_int('n_estimators', 50, 300)
        max_depth = trial.suggest_int('max_depth', 3, 16)
        min_samples_split = trial.suggest_int('min_samples_split', 2, 20)
        min_samples_leaf = trial.suggest_int('min_samples_leaf', 1, 10)
        from sklearn.model_selection import cross_val_score
        from sklearn.ensemble import RandomForestRegressor

        model = RandomForestRegressor(
            n_estimators=int(n_estimators),
            max_depth=int(max_depth),
            min_samples_split=int(min_samples_split),
            min_samples_leaf=int(min_samples_leaf),
            random_state=42,
        )
        # negative MSE -> minimize RMSE
        scores = cross_val_score(model, X, y, scoring='neg_mean_squared_error', cv=3)
        rmse = float(np.sqrt(-scores.mean()))
        return rmse

    study = optuna.create_study(direction='minimize')
    study.optimize(objective, n_trials=int(n_trials))
    return dict(study.best_trial.params)


def tune_xgboost_hyperparams(df: pd.DataFrame, target_col: str = "target", n_trials: int = 20) -> dict:
    """Run a small Optuna study to tune common XGBoost hyperparameters.

    Returns a dict of best parameters. Raises RuntimeError if Optuna not installed.
    """
    try:
        import optuna
    except Exception:
        raise RuntimeError("Optuna not installed. Install with `pip install optuna` to enable tuning")

    if target_col not in df.columns:
        raise ValueError(f"target_col '{target_col}' not in DataFrame")

    X = df.drop(columns=[target_col]).select_dtypes(include=[np.number]).fillna(0)
    y = df[target_col].astype(float).values

    def objective(trial: 'optuna.Trial'):
        n_estimators = trial.suggest_int('n_estimators', 50, 500)
        max_depth = trial.suggest_int('max_depth', 3, 12)
        learning_rate = trial.suggest_float('learning_rate', 0.01, 0.3, log=True)
        subsample = trial.suggest_float('subsample', 0.6, 1.0)
        colsample_bytree = trial.suggest_float('colsample_bytree', 0.5, 1.0)

        try:
            import xgboost as xgb
            from sklearn.model_selection import cross_val_score

            params = {
                'n_estimators': int(n_estimators),
                'max_depth': int(max_depth),
                'learning_rate': float(learning_rate),
                'subsample': float(subsample),
                'colsample_bytree': float(colsample_bytree),
                'random_state': 42,
                'verbosity': 0,
            }
            model = xgb.XGBRegressor(**params)
        except Exception:
            # fallback to sklearn GradientBoosting when xgboost not available
            from sklearn.ensemble import GradientBoostingRegressor
            from sklearn.model_selection import cross_val_score

            params = {
                'n_estimators': int(n_estimators),
                'max_depth': int(max_depth),
                'learning_rate': float(learning_rate),
                'subsample': float(subsample),
            }
            model = GradientBoostingRegressor(**params)

        scores = cross_val_score(model, X, y, scoring='neg_mean_squared_error', cv=3)
        rmse = float(np.sqrt(-scores.mean()))
        return rmse

    study = optuna.create_study(direction='minimize')
    study.optimize(objective, n_trials=int(n_trials))
    return dict(study.best_trial.params)
