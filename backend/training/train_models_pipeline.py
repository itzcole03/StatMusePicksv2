"""Training pipeline (Task 2.1.3)

Purpose:
- Train multiple model families per-player (RandomForest, XGBoost, ElasticNet) when
  sufficient historical data exists (default >=50 games).
- Optionally run Optuna tuning (configurable trials).
- Save best model to legacy `PlayerModelRegistry` and register in the per-version registry.
- Emit a CSV training report with metrics, hyperparameters and version ids.

Notes:
- This module is intended to be non-destructive: it does not replace the existing
  `train_models.py`. It provides a roadmap-aligned training pipeline for Phase 2.
"""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Optional, Any, Tuple

import hashlib
import numpy as np
import pandas as pd
from datetime import datetime

from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import ElasticNet
from sklearn.metrics import mean_absolute_error

try:
    from xgboost import XGBRegressor
except Exception:
    XGBRegressor = None

try:
    import optuna
    OPTUNA_AVAILABLE = True
except Exception:
    optuna = None
    OPTUNA_AVAILABLE = False

import joblib

from backend.services.model_registry import PlayerModelRegistry
from backend.services.training_data_service import time_series_cv_split


def _mae(y_true, y_pred):
    return float(mean_absolute_error(y_true, y_pred))


def _read_dataset(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".csv", ".txt"):
        return pd.read_csv(path)
    return pd.read_parquet(path)


def _select_feature_columns(df: pd.DataFrame):
    exclude = {"player_id", "player_name", "target", "split", "game_date"}
    cols = [c for c in df.columns if c not in exclude]
    numeric = df[cols].select_dtypes(include=["number"]).columns.tolist() if cols else []
    return numeric


def _file_hash(p: Path, algo: str = "sha256") -> str:
    h = hashlib.new(algo)
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _train_and_select(models_to_try: Dict[str, Any], X_train, y_train, X_val, y_val) -> Tuple[str, Any, Dict]:
    """Train candidate models and pick best by validation MAE. Returns (name, model, hyperparams)."""
    best_name = None
    best_model = None
    best_score = None
    best_params = None

    for name, ctor in models_to_try.items():
        try:
            model = ctor()
            model.fit(X_train, y_train)
            preds = model.predict(X_val)
            score = _mae(y_val, preds)
            if best_score is None or score < best_score:
                best_score = score
                best_model = model
                best_name = name
                # best_params: try to capture constructor params if available
                try:
                    best_params = getattr(model, "get_params", lambda: {})()
                except Exception:
                    best_params = {}
        except Exception:
            continue

    return best_name, best_model, (best_params or {})


def _is_synthetic_dataset(df) -> bool:
    """Heuristic check for synthetic / sample datasets.

    Returns True if the dataset appears synthetic (e.g., player names like `player_123`,
    or contains 'toy'/'sample'/'synthetic' markers). Conservative: returns False when
    unsure.
    """
    try:
        import re

        if "player_name" in df.columns:
            names = df["player_name"].dropna().astype(str)
            if len(names) == 0:
                return False
            # proportion of names like player_123
            mask = names.str.match(r"^player_\d+$")
            if float(mask.sum()) / float(len(names)) > 0.5:
                return True
            # presence of toy/sample/synthetic keywords
            if names.str.contains(r"toy|sample|synthetic", case=False, regex=True).any():
                return True
    except Exception:
        return False
    return False


def train_from_dataset_pipeline(dataset_path: str, store_dir: str = "backend/models_store", min_games: int = 50, optuna_trials: int = 0, n_jobs: int = 1, allow_synthetic: bool = False) -> Dict:
    path = Path(dataset_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    df = _read_dataset(path)
    if df.empty:
        raise RuntimeError("Empty dataset")

    # Safety: detect synthetic/sample datasets and abort unless explicitly allowed.
    if _is_synthetic_dataset(df) and not allow_synthetic:
        raise RuntimeError(
            "Refusing to train: dataset appears to be synthetic/sample data. "
            "If you really want to proceed, re-run with --allow-synthetic flag."
        )

    reg = PlayerModelRegistry(store_dir)
    report_rows = []
    dataset_version = _file_hash(path)

    # candidate model constructors (lazy lambdas to allow paramization if needed)
    def rf_ctor():
        return RandomForestRegressor(random_state=0, n_jobs=n_jobs, n_estimators=100)

    def enet_ctor():
        return ElasticNet(random_state=0)

    def xgb_ctor():
        return XGBRegressor(random_state=0, verbosity=0, n_jobs=n_jobs) if XGBRegressor is not None else None

    base_models = {"RandomForest": rf_ctor, "ElasticNet": enet_ctor}
    if XGBRegressor is not None:
        base_models["XGBoost"] = xgb_ctor

    for pid, group in df.groupby("player_id"):
        if len(group) < min_games:
            continue

        # Prefer time-series CV split if available
        try:
            folds = time_series_cv_split(group, n_splits=3, val_size=0.15, test_size=0.15)
        except Exception:
            folds = []

        if folds:
            # Use first fold train/val/test for model selection and final training on train+val
            fold0 = folds[0]
            train = fold0.get("train", pd.DataFrame())
            val = fold0.get("val", pd.DataFrame())
            test = fold0.get("test", pd.DataFrame())
        else:
            # deterministic chronological split if no split column
            grp = group.sort_values("game_date") if "game_date" in group.columns else group
            n = len(grp)
            train_end = int(n * 0.7)
            val_end = train_end + int(n * 0.15)
            train = grp.iloc[:train_end]
            val = grp.iloc[train_end:val_end]
            test = grp.iloc[val_end:]

        if train.empty:
            continue

        feature_cols = _select_feature_columns(group)
        if not feature_cols:
            # fallback baseline
            mean_target = float(group["target"].mean())
            model_obj = {"mean": mean_target}
            player_name = group["player_name"].iloc[0] if "player_name" in group.columns else f"player_{pid}"
            metadata = {
                "model_type": "mean_baseline",
                "notes": f"trained from {path.name}",
                "metrics": {},
                "feature_columns": [],
                "hyperparameters": None,
                "dataset_version": dataset_version,
            }
            version = reg.save_model(player_name, model_obj, metadata=metadata)
            report_rows.append({
                "player_id": pid,
                "player_name": player_name,
                "chosen_model": "mean_baseline",
                "version": version,
                "val_mae": None,
                "test_mae": None,
            })
            continue

        X_train = train[feature_cols].to_numpy()
        y_train = train["target"].to_numpy()
        X_val = val[feature_cols].to_numpy() if not val.empty else X_train
        y_val = val["target"].to_numpy() if not val.empty else y_train
        X_test = test[feature_cols].to_numpy() if not test.empty else None
        y_test = test["target"].to_numpy() if not test.empty else None

        # If optuna requested, run a per-player lightweight optimization for RF only (XGB & ENet optional)
        optuna_result_for_player = None
        optuna_full_for_player = None
        if OPTUNA_AVAILABLE and optuna_trials and optuna_trials > 0:
            try:
                def objective(trial):
                    n_estimators = trial.suggest_int("n_estimators", 50, 150)
                    max_depth = trial.suggest_categorical("max_depth", [None, 5, 10])
                    est = RandomForestRegressor(random_state=0, n_jobs=1, n_estimators=n_estimators, max_depth=max_depth)
                    est.fit(X_train, y_train)
                    pred = est.predict(X_val)
                    return _mae(y_val, pred)

                study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=0))
                study.optimize(objective, n_trials=optuna_trials, show_progress_bar=False)
                best_params = study.best_params
                # persist a lightweight serializable representation of the study
                        try:
                            trials_list = []
                            for t in study.trials:
                                trials_list.append({
                                    "number": int(t.number),
                                    "value": float(t.value) if t.value is not None else None,
                                    "params": {k: (v.tolist() if hasattr(v, 'tolist') else v) for k, v in (t.params or {}).items()},
                                    "state": str(t.state),
                                })
                            optuna_result_for_player = {
                                "best_params": best_params,
                                "best_value": float(study.best_value) if study.best_value is not None else None,
                                "trials": trials_list,
                            }
                            # try to capture a fuller trials dataframe for CSV/JSON persistence
                            try:
                                df = study.trials_dataframe()
                                optuna_full_for_player = df.to_dict(orient="records")
                            except Exception:
                                optuna_full_for_player = trials_list
                        except Exception:
                            optuna_result_for_player = {"best_params": best_params, "best_value": None, "trials": []}
                            optuna_full_for_player = None
                # replace RF constructor with tuned params
                def rf_tuned_ctor():
                    return RandomForestRegressor(random_state=0, n_jobs=n_jobs, **best_params)

                models = {**base_models, "RandomForest": rf_tuned_ctor}
            except Exception:
                models = base_models
        else:
            models = base_models

        # Train candidate models & select best on val
        chosen_name, chosen_model, chosen_params = _train_and_select(models, X_train, y_train, X_val, y_val)

        if chosen_model is None:
            # fallback to mean baseline
            mean_target = float(group["target"].mean())
            model_obj = {"mean": mean_target}
            player_name = group["player_name"].iloc[0] if "player_name" in group.columns else f"player_{pid}"
            metadata = {
                "model_type": "mean_baseline",
                "notes": f"fallback baseline from {path.name}",
                "metrics": {},
                "feature_columns": feature_cols,
                "hyperparameters": None,
                "dataset_version": dataset_version,
            }
            version = reg.save_model(player_name, model_obj, metadata=metadata)
            report_rows.append({
                "player_id": pid,
                "player_name": player_name,
                "chosen_model": "mean_baseline",
                "version": version,
                "val_mae": None,
                "test_mae": None,
            })
            continue

        # evaluate on test
        val_mae = _mae(y_val, chosen_model.predict(X_val)) if X_val is not None else None
        test_mae = _mae(y_test, chosen_model.predict(X_test)) if (X_test is not None and y_test is not None) else None

        player_name = group["player_name"].iloc[0] if "player_name" in group.columns else f"player_{pid}"
        metadata = {
            "model_type": f"{chosen_name}:{type(chosen_model).__name__}",
            "notes": f"trained from {path.name}",
            "metrics": {k: v for k, v in (("val_mae", val_mae), ("test_mae", test_mae)) if v is not None},
            "feature_columns": feature_cols,
            "hyperparameters": chosen_params,
            "feature_importances": None,
            "dataset_version": dataset_version,
            "optuna_study": optuna_result_for_player,
        }

        version = reg.save_model(player_name, chosen_model, metadata=metadata)

        # register with per-version registry if available (best-effort)
        try:
            from backend.services.simple_model_registry import ModelRegistry as SimpleRegistry

            safe = player_name.replace(" ", "_")
            fname = f"{safe}_v{version}.joblib"
            artifact_path = Path(store_dir) / fname
            sreg = SimpleRegistry(base_path=Path(store_dir))
            meta = sreg.register_model(player_name, artifact_src=artifact_path, metadata={**(metadata or {}), "registered_by": "train_models_pipeline"})
            # persist Optuna study JSON alongside the version metadata if available
            try:
                if optuna_full_for_player is not None:
                    version_dir = Path(sreg.base_path) / player_name / "versions" / meta.version_id
                    version_dir.mkdir(parents=True, exist_ok=True)
                    opt_path = version_dir / "optuna_study.json"
                    # sanitize entries to ensure JSON serializable values (timestamps, numpy types)
                    def _sanitize_obj(o):
                        if o is None:
                            return None
                        if isinstance(o, (str, bool, int, float)):
                            return o
                        if isinstance(o, (np.generic,)):
                            try:
                                return o.item()
                            except Exception:
                                return str(o)
                        if isinstance(o, (list, tuple)):
                            return [_sanitize_obj(x) for x in o]
                        if isinstance(o, dict):
                            return {str(k): _sanitize_obj(v) for k, v in o.items()}
                        # pandas / numpy datetimes and python datetimes
                        try:
                            import pandas as _pd
                            if isinstance(o, (_pd.Timestamp, datetime)):
                                return o.isoformat()
                        except Exception:
                            pass
                        try:
                            # fallback convert to string
                            return str(o)
                        except Exception:
                            return None

                    sanitized_full = [_sanitize_obj(r) for r in optuna_full_for_player]
                    with open(opt_path, "w", encoding="utf-8") as fh:
                        json.dump({"summary": _sanitize_obj(optuna_result_for_player), "trials": sanitized_full}, fh, indent=2)
                    # also write trials as CSV for easy inspection
                    try:
                        df_trials = pd.DataFrame(sanitized_full)
                        csv_path = version_dir / "optuna_trials.csv"
                        df_trials.to_csv(csv_path, index=False)
                    except Exception:
                        pass
            except Exception:
                # best-effort: do not fail the training if writing study fails
                pass
        except Exception:
            pass

        report_rows.append({
            "player_id": pid,
            "player_name": player_name,
            "chosen_model": chosen_name,
            "version": version,
            "val_mae": val_mae,
            "test_mae": test_mae,
            "hyperparameters": json.dumps(chosen_params),
        })

    # write CSV report
    report_path = Path(store_dir) / f"training_report_{path.stem}.csv"
    with open(report_path, "w", newline="", encoding="utf-8") as csvfile:
        if report_rows:
            writer = csv.DictWriter(csvfile, fieldnames=report_rows[0].keys())
            writer.writeheader()
            for r in report_rows:
                writer.writerow(r)

    # also write JSON summary
    summary_path = Path(store_dir) / f"training_summary_{path.stem}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({r["player_name"]: {"version": r["version"], "metrics": {"val_mae": r.get("val_mae"), "test_mae": r.get("test_mae")}} for r in report_rows}, f, indent=2)

    return {r["player_name"]: {"version": r["version"], "val_mae": r.get("val_mae"), "test_mae": r.get("test_mae")} for r in report_rows}


def _cli():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", required=True, help="Path to dataset file (CSV or parquet)")
    p.add_argument("--store-dir", default="backend/models_store")
    p.add_argument("--min-games", type=int, default=50)
    p.add_argument("--optuna-trials", type=int, default=0)
    p.add_argument("--n-jobs", type=int, default=1)
    p.add_argument("--allow-synthetic", action="store_true", help="Allow training on datasets that appear synthetic/sample (unsafe)" )
    args = p.parse_args()
    res = train_from_dataset_pipeline(args.dataset, args.store_dir, args.min_games, args.optuna_trials, args.n_jobs, allow_synthetic=args.allow_synthetic)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    _cli()
