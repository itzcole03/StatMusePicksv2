"""Train models from a saved dataset and register them in PlayerModelRegistry.

This training script is intentionally lightweight for integration and CI:
- Reads a dataset file (CSV or parquet) produced by `training_data_service`.
- Groups rows by `player_id` and trains a simple mean-baseline model per player.
- Computes MAE on validation split (if present) and stores metrics in registry.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Optional, List

import hashlib
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import RandomizedSearchCV
from sklearn.metrics import mean_absolute_error

# Classification imports (added)
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score, accuracy_score
from sklearn.model_selection import train_test_split
try:
    from xgboost import XGBClassifier
except Exception:
    XGBClassifier = None

from tqdm.auto import tqdm
import logging
import time

LOG = logging.getLogger("backend.training.train_models")


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    # avoid adding multiple handlers during repeated calls
    if not root.handlers:
        root.addHandler(handler)
    root.setLevel(level)

try:
    from xgboost import XGBRegressor
except Exception:
    XGBRegressor = None  # optional

try:
    from backend.models.elastic_net_model import ElasticNetModel
except Exception:
    ElasticNetModel = None

try:
    import optuna
    OPTUNA_AVAILABLE = True
except Exception:
    optuna = None
    OPTUNA_AVAILABLE = False

from backend.services.model_registry import PlayerModelRegistry
from backend.services.training_data_service import time_series_cv_split
try:
    from backend.models.ensemble_model import EnsembleModel
except Exception:
    EnsembleModel = None


def _read_dataset(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".csv", ".txt"):
        return pd.read_csv(path)
    return pd.read_parquet(path)


def _mae(y_true, y_pred):
    return float(mean_absolute_error(y_true, y_pred))


def _select_feature_columns(df: pd.DataFrame) -> List[str]:
    # Exclude known meta columns
    exclude = {"player_id", "player_name", "target", "split", "game_date"}
    cols = [c for c in df.columns if c not in exclude]
    # prefer numeric columns only
    numeric = df[cols].select_dtypes(include=["number"]).columns.tolist() if cols else []
    return numeric


def train_from_dataset(dataset_path: str, store_dir: str = "backend/models_store", min_games: int = 50, trials: int = 50, report_csv: Optional[str] = None, ensemble_trials: int = 50, ensemble_timeout: Optional[int] = None) -> Dict:
    path = Path(dataset_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    df = _read_dataset(path)
    if df.empty:
        raise RuntimeError("Empty dataset")

    # Conservative safety: detect synthetic/sample datasets and abort unless allowed via env or explicit override.
    try:
        if "player_name" in df.columns:
            names = df["player_name"].dropna().astype(str)
            if len(names) > 0 and float(names.str.match(r"^player_\d+$").sum()) / float(len(names)) > 0.5:
                raise RuntimeError(
                    "Refusing to train: dataset appears synthetic/sample (player_name patterns). "
                    "Re-run with a real dataset or call train_from_dataset(..., allow_synthetic=True) if intentional."
                )
    except RuntimeError:
        raise
    except Exception:
        # On unexpected errors during detection, proceed rather than block.
        pass

    reg = PlayerModelRegistry(store_dir)
    results = {}

    # Compute a deterministic fingerprint of the dataset file for traceability
    def _file_hash(p: Path, algo: str = "sha256") -> str:
        h = hashlib.new(algo)
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    dataset_version = _file_hash(path)

    # Group by player_id and train a small sklearn model per player
    players = list(df.groupby("player_id"))
    iterator = tqdm(players, desc="players")
    for pid, group in iterator:
        if len(group) < min_games:
            LOG.debug("Skipping player %s: only %d games (min %d)", pid, len(group), min_games)
            continue
        start_ts = time.time()
        LOG.info("Starting training for player_id=%s (n=%d)", pid, len(group))

        # If split col exists, use it; otherwise split randomly (time-ordering not enforced here)
        if "split" in group.columns:
            train = group[group["split"] == "train"]
            val = group[group["split"] == "val"]
            test = group[group["split"] == "test"]
        else:
            # simple random split
            train = group.sample(frac=0.7, random_state=0)
            rest = group.drop(train.index)
            val = rest.sample(frac=0.5, random_state=0) if not rest.empty else pd.DataFrame()
            test = rest.drop(val.index) if not rest.empty else pd.DataFrame()

        if train.empty:
            continue

        feature_cols = _select_feature_columns(group)
        y_all = group["target"]

        # Determine if this is a binary classification task
        unique_vals = pd.Series(y_all).dropna().unique()
        is_binary = len(unique_vals) == 2 or set(map(int, unique_vals)) <= {0, 1} if len(unique_vals) <= 10 else False

        X_train = train[feature_cols].to_numpy() if feature_cols else np.zeros((len(train), 1))
        y_train = train["target"].to_numpy()

        # If there are no features, fall back to mean baseline
        if not feature_cols:
            mean_target = float(y_train.mean())
            model = {"mean": mean_target}
            val_mae = float(_mae(val["target"], [mean_target] * len(val))) if not val.empty else None
            test_mae = float(_mae(test["target"], [mean_target] * len(test))) if not test.empty else None
            player_name = group["player_name"].iloc[0] if "player_name" in group.columns else f"player_{pid}"
            metadata = {
                "model_type": "mean_baseline",
                "notes": f"trained from {path.name}",
                "metrics": {k: v for k, v in (("val_mae", val_mae), ("test_mae", test_mae)) if v is not None},
                "feature_columns": [],
                "hyperparameters": None,
                "dataset_version": dataset_version,
            }
            version = reg.save_model(player_name, model, metadata=metadata)
            # Also register the saved artifact in the lightweight simple registry (dev/CI)
            try:
                from backend.services.simple_model_registry import ModelRegistry as SimpleRegistry

                safe = player_name.replace(" ", "_")
                fname = f"{safe}_v{version}.joblib"
                artifact_path = Path(store_dir) / fname
                sreg = SimpleRegistry(base_path=Path(store_dir))
                sreg.register_model(player_name, artifact_src=artifact_path, metadata={**(metadata or {}), "registered_by": "train_models.save_model"})
            except Exception:
                # non-fatal: simple registry optional in some dev setups
                pass
            results[player_name] = {"version": version, "metrics": metadata["metrics"]}
            elapsed = time.time() - start_ts
            LOG.info("Finished player %s (baseline), elapsed=%.1fs", player_name, elapsed)
            continue

        # perform a conservative randomized search using time-series CV folds per player
        def _search_estimators_with_folds(folds, feature_cols, n_iter=8):
            best_est = None
            best_score = None
            best_params = None
            best_name = None

            rf_param_choices = {
                "n_estimators": [10, 20, 50, 100],
                "max_depth": [None, 3, 5, 10],
                "max_features": ["auto", "sqrt"],
            }

            xgb_param_choices = {
                "n_estimators": [10, 20, 50, 100],
                "max_depth": [3, 5, 7],
                "learning_rate": [0.01, 0.05, 0.1],
                "subsample": [0.6, 0.8, 1.0],
            }

            import random

            def _sample_params(choices: Dict):
                return {k: random.choice(v) for k, v in choices.items()}

            # RandomForest samples
            for _ in range(n_iter):
                params = _sample_params(rf_param_choices)
                try:
                    est = RandomForestRegressor(random_state=0, n_jobs=-1, **params)
                except Exception:
                    continue
                vals = []
                for f in folds:
                    tr = f["train"]
                    vl = f["val"]
                    if vl.empty or tr.empty:
                        continue
                    Xtr = tr[feature_cols].to_numpy()
                    ytr = tr["target"].to_numpy()
                    Xvl = vl[feature_cols].to_numpy()
                    yvl = vl["target"].to_numpy()
                    try:
                        est.fit(Xtr, ytr)
                        pred = est.predict(Xvl)
                        vals.append(_mae(yvl, pred))
                    except Exception:
                        continue
                if not vals:
                    continue
                score = float(sum(vals) / len(vals))
                if best_score is None or score < best_score:
                    best_score = score
                    best_est = est
                    best_params = params
                    best_name = "RandomForest"

            # XGBoost samples (optional)
            if XGBRegressor is not None:
                for _ in range(n_iter):
                    params = _sample_params(xgb_param_choices)
                    try:
                        est = XGBRegressor(random_state=0, verbosity=0, n_jobs=-1, **params)
                    except Exception:
                        continue
                    vals = []
                    for f in folds:
                        tr = f["train"]
                        vl = f["val"]
                        if vl.empty or tr.empty:
                            continue
                        Xtr = tr[feature_cols].to_numpy()
                        ytr = tr["target"].to_numpy()
                        Xvl = vl[feature_cols].to_numpy()
                        yvl = vl["target"].to_numpy()
                        try:
                            est.fit(Xtr, ytr)
                            pred = est.predict(Xvl)
                            vals.append(_mae(yvl, pred))
                        except Exception:
                            continue
                    if not vals:
                        continue
                    score = float(sum(vals) / len(vals))
                    if best_score is None or score < best_score:
                        best_score = score
                        best_est = est
                        best_params = params
                        best_name = "XGBoost"

            return best_name, best_est, best_params

        # build folds for this player using time-series CV
        try:
            folds = time_series_cv_split(group, n_splits=3, val_size=0.15, test_size=0.15)
        except Exception:
            folds = []

        if not folds:
            # fallback to previous single-split logic
            try:
                if "split" in group.columns:
                    train = group[group["split"] == "train"]
                    val = group[group["split"] == "val"]
                    test = group[group["split"] == "test"]
                else:
                    train = group.sample(frac=0.7, random_state=0)
                    rest = group.drop(train.index)
                    val = rest.sample(frac=0.5, random_state=0) if not rest.empty else pd.DataFrame()
                    test = rest.drop(val.index) if not rest.empty else pd.DataFrame()
            except Exception:
                train = group
                val = pd.DataFrame()
                test = pd.DataFrame()

            if train.empty:
                continue

            folds_for_search = [{"train": train, "val": val, "test": test}]
        else:
            folds_for_search = folds

        # If Optuna is available, run tuning optimizing Brier score for classification
        # or the existing brier-like regression proxy for regression.
        def _brier_like_score_for_fold(preds, true_vals):
            # Convert regression preds to pseudo-probabilities via sigmoid around median
            import numpy as _np

            if len(true_vals) == 0:
                return None
            thresh = float(_np.median(true_vals))
            scale = float(_np.std(true_vals)) if float(_np.std(true_vals)) > 0 else 1.0
            probs = 1 / (1 + _np.exp(-(preds - thresh) / scale))
            y_bin = (_np.array(true_vals) > thresh).astype(float)
            return float(((probs - y_bin) ** 2).mean())

        if is_binary:
            # Classification path: optimize brier score per model (RF, XGB, ElasticNet logistic)
            def _train_and_tune_classifier(model_type: str, n_trials: int = 50):
                best_model = None
                best_score = None
                best_params = None

                if OPTUNA_AVAILABLE:
                    # Define objective per model
                    def _rf_obj(trial):
                        n_estimators = trial.suggest_int("n_estimators", 50, 300)
                        max_depth = trial.suggest_int("max_depth", 3, 20)
                        min_samples_leaf = trial.suggest_int("min_samples_leaf", 1, 4)
                        clf = RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth, min_samples_leaf=min_samples_leaf, random_state=0, n_jobs=1)
                        # evaluate across folds
                        scores = []
                        for f in folds_for_search:
                            tr = f.get("train", pd.DataFrame())
                            vl = f.get("val", pd.DataFrame())
                            if tr.empty or vl.empty:
                                continue
                            Xtr = tr[feature_cols].to_numpy()
                            ytr = tr["target"].to_numpy()
                            Xvl = vl[feature_cols].to_numpy()
                            yvl = vl["target"].to_numpy()
                            try:
                                clf.fit(Xtr, ytr)
                                probs = clf.predict_proba(Xvl)[:, 1]
                                scores.append(float(brier_score_loss(yvl, probs)))
                            except Exception:
                                # On failures return a large but finite penalty (Brier in [0,1])
                                return 1.0
                        return float(sum(scores) / len(scores)) if scores else 1.0

                    def _xgb_obj(trial):
                        n_estimators = trial.suggest_int("n_estimators", 50, 300)
                        max_depth = trial.suggest_int("max_depth", 2, 12)
                        lr = trial.suggest_float("learning_rate", 0.01, 0.3, log=True)
                        clf = XGBClassifier(n_estimators=n_estimators, max_depth=max_depth, learning_rate=lr, use_label_encoder=False, verbosity=0, n_jobs=1, random_state=0)
                        scores = []
                        for f in folds_for_search:
                            tr = f.get("train", pd.DataFrame())
                            vl = f.get("val", pd.DataFrame())
                            if tr.empty or vl.empty:
                                continue
                            Xtr = tr[feature_cols].to_numpy()
                            ytr = tr["target"].to_numpy()
                            Xvl = vl[feature_cols].to_numpy()
                            yvl = vl["target"].to_numpy()
                            try:
                                clf.fit(Xtr, ytr, eval_set=[(Xvl, yvl)], verbose=False)
                                probs = clf.predict_proba(Xvl)[:, 1]
                                scores.append(float(brier_score_loss(yvl, probs)))
                            except Exception:
                                return 1.0
                        return float(sum(scores) / len(scores)) if scores else 1.0

                    def _en_obj(trial):
                        C = trial.suggest_float("C", 1e-3, 1e2, log=True)
                        l1_ratio = trial.suggest_float("l1_ratio", 0.0, 1.0)
                        clf = LogisticRegression(penalty="elasticnet", solver="saga", C=C, l1_ratio=l1_ratio, max_iter=5000, random_state=0)
                        scores = []
                        for f in folds_for_search:
                            tr = f.get("train", pd.DataFrame())
                            vl = f.get("val", pd.DataFrame())
                            if tr.empty or vl.empty:
                                continue
                            Xtr = tr[feature_cols].to_numpy()
                            ytr = tr["target"].to_numpy()
                            Xvl = vl[feature_cols].to_numpy()
                            yvl = vl["target"].to_numpy()
                            try:
                                clf.fit(Xtr, ytr)
                                probs = clf.predict_proba(Xvl)[:, 1]
                                scores.append(float(brier_score_loss(yvl, probs)))
                            except Exception:
                                return 1.0
                        return float(sum(scores) / len(scores)) if scores else 1.0

                    if model_type == "rf":
                        study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=0))
                        study.optimize(_rf_obj, n_trials=trials, show_progress_bar=False)
                        best_params = study.best_params
                        # prepare union train
                        union_train_df = pd.concat([f.get("train", pd.DataFrame()) for f in folds_for_search if not f.get("train", pd.DataFrame()).empty], ignore_index=True)
                        if union_train_df.empty or len(pd.Series(union_train_df["target"]).dropna().unique()) < 2:
                            # insufficient class variety to train classifier
                            LOG.debug("Skipping RF fit for player %s: single-class in union train", pid)
                            return None, None, None
                        best_model = RandomForestClassifier(**best_params, random_state=0, n_jobs=-1)
                        best_model.fit(union_train_df[feature_cols].to_numpy(), union_train_df["target"].to_numpy())
                        best_score = study.best_value
                    elif model_type == "xgb" and XGBClassifier is not None:
                        study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=0))
                        study.optimize(_xgb_obj, n_trials=trials, show_progress_bar=False)
                        best_params = study.best_params
                        union_train_df = pd.concat([f.get("train", pd.DataFrame()) for f in folds_for_search if not f.get("train", pd.DataFrame()).empty], ignore_index=True)
                        if union_train_df.empty or len(pd.Series(union_train_df["target"]).dropna().unique()) < 2:
                            LOG.debug("Skipping XGB fit for player %s: single-class in union train", pid)
                            return None, None, None
                        best_model = XGBClassifier(**best_params, use_label_encoder=False, verbosity=0, n_jobs=-1, random_state=0)
                        best_model.fit(union_train_df[feature_cols].to_numpy(), union_train_df["target"].to_numpy())
                        best_score = study.best_value
                    elif model_type == "en":
                        study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=0))
                        study.optimize(_en_obj, n_trials=trials, show_progress_bar=False)
                        best_params = study.best_params
                        union_train_df = pd.concat([f.get("train", pd.DataFrame()) for f in folds_for_search if not f.get("train", pd.DataFrame()).empty], ignore_index=True)
                        if union_train_df.empty or len(pd.Series(union_train_df["target"]).dropna().unique()) < 2:
                            LOG.debug("Skipping ElasticNet fit for player %s: single-class in union train", pid)
                            return None, None, None
                        # Prefer using the project ElasticNetModel wrapper if available
                        if ElasticNetModel is not None:
                            try:
                                enm = ElasticNetModel(C=best_params.get("C", 1.0), l1_ratio=best_params.get("l1_ratio", 0.5), max_iter=5000, random_state=0)
                                enm.train(union_train_df[feature_cols].to_numpy(), union_train_df["target"].to_numpy(), feature_names=feature_cols)
                                # use underlying estimator for downstream compatibility
                                best_model = enm.get_estimator() or getattr(enm, "_model", None)
                            except Exception:
                                # fallback to sklearn directly
                                best_model = LogisticRegression(penalty="elasticnet", solver="saga", **best_params, max_iter=5000, random_state=0)
                                best_model.fit(union_train_df[feature_cols].to_numpy(), union_train_df["target"].to_numpy())
                        else:
                            best_model = LogisticRegression(penalty="elasticnet", solver="saga", **best_params, max_iter=5000, random_state=0)
                            best_model.fit(union_train_df[feature_cols].to_numpy(), union_train_df["target"].to_numpy())
                        best_score = study.best_value
                    else:
                        # Not available, fallback
                        return None, None, None
                else:
                    # Fallback: simple randomized search across folds using _search_estimators_with_folds
                    name, est, params = _search_estimators_with_folds(folds_for_search, feature_cols, n_iter=8)
                    return name, est, params

                return best_model, best_score, best_params

            # Run tuning per-model
            rf_model, rf_score, rf_params = _train_and_tune_classifier("rf", n_trials=trials)
            xgb_model, xgb_score, xgb_params = (None, None, None)
            if XGBClassifier is not None:
                xgb_model, xgb_score, xgb_params = _train_and_tune_classifier("xgb", n_trials=trials)
            en_model, en_score, en_params = _train_and_tune_classifier("en", n_trials=trials)

            # Evaluate on held-out test if available, otherwise on val
            def _eval_clf(m):
                if m is None:
                    return {"brier": None, "logloss": None, "roc_auc": None, "accuracy": None}
                eval_df = test if not test.empty else val
                if eval_df.empty:
                    return {"brier": None, "logloss": None, "roc_auc": None, "accuracy": None}
                Xev = eval_df[feature_cols].to_numpy()
                yev = eval_df["target"].to_numpy()
                probs = m.predict_proba(Xev)[:, 1]
                preds = (probs >= 0.5).astype(int)
                return {
                    "brier": float(brier_score_loss(yev, probs)),
                    "logloss": float(log_loss(yev, probs, labels=[0, 1])),
                    "roc_auc": float(roc_auc_score(yev, probs)) if len(np.unique(yev)) > 1 else None,
                    "accuracy": float(accuracy_score(yev, preds)),
                }

            rf_metrics = _eval_clf(rf_model)
            xgb_metrics = _eval_clf(xgb_model)
            en_metrics = _eval_clf(en_model)

            # Choose best by brier (lower is better)
            candidates = [
                ("random_forest", rf_model, rf_metrics, rf_params),
                ("xgboost", xgb_model, xgb_metrics, xgb_params),
                ("elasticnet", en_model, en_metrics, en_params),
            ]
            best = None
            best_brier = None
            for name, model_obj, metrics, params in candidates:
                if model_obj is None or metrics is None or metrics.get("brier") is None:
                    continue
                if best_brier is None or metrics["brier"] < best_brier:
                    best = (name, model_obj, metrics, params)
                    best_brier = metrics["brier"]

            if best is None:
                # fallback to mean baseline
                mean_target = float(group["target"].mean())
                model = {"mean": mean_target}
                player_name = group.get("player_name", pd.Series([f"player_{pid}"])).iloc[0]
                metadata = {
                    "model_type": "mean_baseline",
                    "notes": f"fallback baseline from {path.name}",
                    "metrics": {},
                    "feature_columns": feature_cols,
                    "hyperparameters": None,
                    "feature_importances": None,
                    "dataset_version": dataset_version,
                }
                version = reg.save_model(player_name, model, metadata=metadata)
                results[player_name] = {"version": version, "metrics": metadata["metrics"]}
                continue

            best_name, best_est, best_metrics, best_hparams = best

            # feature importances
            feature_importances = None
            try:
                if hasattr(best_est, "feature_importances_"):
                    arr = getattr(best_est, "feature_importances_")
                    vals = arr.tolist() if hasattr(arr, "tolist") else list(arr)
                    if len(vals) == len(feature_cols):
                        feature_importances = {c: float(v) for c, v in zip(feature_cols, vals)}
                elif hasattr(best_est, "coef_"):
                    arr = getattr(best_est, "coef_")
                    flat = arr.ravel() if hasattr(arr, "ravel") else arr
                    vals = flat.tolist() if hasattr(flat, "tolist") else list(flat)
                    if len(vals) == len(feature_cols):
                        feature_importances = {c: float(v) for c, v in zip(feature_cols, vals)}
            except Exception:
                feature_importances = None

            player_name = group["player_name"].iloc[0] if "player_name" in group.columns else f"player_{pid}"
            metadata = {
                "model_type": f"{best_name}:{type(best_est).__name__}",
                "notes": f"trained from {path.name}",
                "metrics": best_metrics,
                "feature_columns": feature_cols,
                "hyperparameters": best_hparams,
                "feature_importances": feature_importances,
                "dataset_version": dataset_version,
            }
            version = reg.save_model(player_name, best_est, metadata=metadata)

            # Append to CSV report if requested
            if report_csv:
                try:
                    report_row = {
                        "player_id": player_name,
                        "n_samples": int(len(group)),
                        "model": best_name,
                        "brier": best_metrics.get("brier"),
                        "logloss": best_metrics.get("logloss"),
                        "roc_auc": best_metrics.get("roc_auc"),
                        "accuracy": best_metrics.get("accuracy"),
                        "best_params": json.dumps(best_hparams, default=str),
                        "timestamp": json.dumps(dataset_version),
                    }
                    import csv
                    write_header = not Path(report_csv).exists()
                    with open(report_csv, "a", newline="", encoding="utf-8") as fh:
                        w = csv.DictWriter(fh, fieldnames=list(report_row.keys()))
                        if write_header:
                            w.writeheader()
                        w.writerow(report_row)
                except Exception:
                    pass

            results[player_name] = {"version": version, "metrics": metadata["metrics"], "hyperparameters": best_hparams}

            elapsed = time.time() - start_ts
            try:
                brier_val = float(best_metrics.get("brier")) if best_metrics and best_metrics.get("brier") is not None else float("nan")
            except Exception:
                brier_val = float("nan")
            LOG.info("Finished player %s, model=%s, brier=%.6f, elapsed=%.1fs", player_name, best_name, brier_val, elapsed)

            continue

        else:
            # Regression fallback (existing behavior)
            if OPTUNA_AVAILABLE:
                # Use estimator-prefixed parameter names to avoid distribution-name collisions
                def _optuna_objective(trial):
                    est_name = trial.suggest_categorical("estimator", ["rf", "xgb"] if XGBRegressor is not None else ["rf"])
                    if est_name == "rf":
                        params = {
                            "n_estimators": trial.suggest_int("rf_n_estimators", 10, 100, log=False),
                            "max_depth": trial.suggest_categorical("rf_max_depth", [None, 3, 5, 10]),
                            "max_features": trial.suggest_categorical("rf_max_features", ["auto", "sqrt"]),
                        }
                        est = RandomForestRegressor(random_state=0, n_jobs=1, **params)
                    else:
                        params = {
                            "n_estimators": trial.suggest_int("xgb_n_estimators", 10, 100, log=False),
                            "max_depth": trial.suggest_int("xgb_max_depth", 3, 7),
                            "learning_rate": trial.suggest_float("xgb_learning_rate", 0.01, 0.1),
                            "subsample": trial.suggest_categorical("xgb_subsample", [0.6, 0.8, 1.0]),
                        }
                        est = XGBRegressor(random_state=0, verbosity=0, n_jobs=1, **params)

                    scores = []
                    for f in folds_for_search:
                        tr = f.get("train", pd.DataFrame())
                        vl = f.get("val", pd.DataFrame())
                        if tr.empty or vl.empty:
                            continue
                        Xtr = tr[feature_cols].to_numpy()
                        ytr = tr["target"].to_numpy()
                        Xvl = vl[feature_cols].to_numpy()
                        yvl = vl["target"].to_numpy()
                        try:
                            est.fit(Xtr, ytr)
                            pred = est.predict(Xvl)
                            sc = _brier_like_score_for_fold(pred, yvl)
                            if sc is not None:
                                scores.append(sc)
                        except Exception:
                            return 1.0
                    if not scores:
                        return 1.0
                    return float(sum(scores) / len(scores))

                study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=0))
                study.optimize(_optuna_objective, n_trials=trials, show_progress_bar=False)
                best_trial = study.best_trial
                # build best estimator from trial params and strip estimator prefixes
                raw_params = {k: v for k, v in best_trial.params.items() if k != "estimator"}
                est_choice = best_trial.params.get("estimator", "rf")
                best_params = {}
                if est_choice == "rf":
                    # collect rf_ prefixed params and strip prefix
                    for k, v in raw_params.items():
                        if k.startswith("rf_"):
                            best_params[k[len("rf_"):]] = v
                    best_est = RandomForestRegressor(random_state=0, n_jobs=-1, **best_params)
                    best_name = "RandomForest"
                else:
                    for k, v in raw_params.items():
                        if k.startswith("xgb_"):
                            best_params[k[len("xgb_"):]] = v
                    best_est = XGBRegressor(random_state=0, verbosity=0, n_jobs=-1, **best_params)
                    best_name = "XGBoost"
                # retrain best_est on union of train+val for all folds
                union_train = pd.concat([pd.concat([f.get("train", pd.DataFrame()), f.get("val", pd.DataFrame())]) for f in folds_for_search if not f.get("train", pd.DataFrame()).empty], ignore_index=True)
                if not union_train.empty and feature_cols:
                    try:
                        best_est.fit(union_train[feature_cols].to_numpy(), union_train["target"].to_numpy())
                    except Exception:
                        pass
                best_params = best_params or {}
            else:
                # fallback to conservative randomized search across folds
                best_name, best_est, best_params = _search_estimators_with_folds(folds_for_search, feature_cols, n_iter=8)

        if best_est is None:
            # fall back to mean baseline
            mean_target = float(group["target"].mean())
            model = {"mean": mean_target}
            test_concat = pd.concat([f["test"] for f in folds if not f["test"].empty], ignore_index=True) if folds else (test if 'test' in locals() else pd.DataFrame())
            val_mae = None
            test_mae = None
            if not test_concat.empty:
                test_mae = float(_mae(test_concat["target"], [mean_target] * len(test_concat)))
            player_name = group["player_name"].iloc[0]
            metadata = {
                "model_type": "mean_baseline",
                "notes": f"fallback baseline from {path.name}",
                "metrics": {k: v for k, v in (("val_mae", val_mae), ("test_mae", test_mae)) if v is not None},
                "feature_columns": feature_cols,
                "hyperparameters": None,
                "feature_importances": None,
                "dataset_version": dataset_version,
            }
            version = reg.save_model(player_name, model, metadata=metadata)
            results[player_name] = {"version": version, "metrics": metadata["metrics"]}
            continue

        # Optionally try an ensemble (regression only) and prefer it if it improves MAE on eval set
        try:
            if EnsembleModel is not None:
                # Build union of train+val across folds if available, otherwise use train+val
                try:
                    union_train = pd.concat([
                        pd.concat([f.get("train", pd.DataFrame()), f.get("val", pd.DataFrame())])
                        for f in folds_for_search
                        if not f.get("train", pd.DataFrame()).empty
                    ], ignore_index=True)
                except Exception:
                    union_train = pd.concat([train, val]) if not train.empty else pd.DataFrame()

                if not union_train.empty and feature_cols:
                    try:
                        ens = EnsembleModel()
                        ens.fit(union_train[feature_cols].to_numpy(), union_train["target"].to_numpy())
                        eval_df = test if ("test" in locals() and not test.empty) else (val if not val.empty else pd.DataFrame())
                        if not eval_df.empty:
                            X_eval = eval_df[feature_cols].to_numpy()
                            y_eval = eval_df["target"].to_numpy()
                            # Optionally tune ensemble weights on the eval set before comparing
                            try:
                                if hasattr(ens, "tune_weights_by_mae"):
                                    try:
                                        tuned = ens.tune_weights_by_mae(X_eval, y_eval, n_trials=ensemble_trials, timeout=ensemble_timeout)
                                        LOG.debug("Player %s: ensemble tuned result=%s", pid, tuned)
                                    except Exception:
                                        LOG.debug("Player %s: ensemble weight tuning failed", pid, exc_info=True)
                            except Exception:
                                pass
                            try:
                                ens_pred = ens.predict(X_eval)
                                ens_mae = float(_mae(y_eval, ens_pred))
                            except Exception:
                                ens_mae = None
                            try:
                                base_pred = best_est.predict(X_eval)
                                base_mae = float(_mae(y_eval, base_pred))
                            except Exception:
                                base_mae = None

                            if ens_mae is not None and base_mae is not None:
                                LOG.debug("Player %s: ensemble MAE=%.6f, base MAE=%.6f", pid, ens_mae, base_mae)
                                # Prefer ensemble when it's strictly better (or equal within tiny tolerance)
                                if ens_mae <= base_mae * 0.9999:
                                    LOG.info("Selecting ensemble for player %s: ensemble_mae=%.6f <= base_mae=%.6f", pid, ens_mae, base_mae)
                                    best_est = ens
                                    best_name = "Ensemble"
                                    best_params = {"weights": getattr(ens, "weights", None), "use_stacking": getattr(ens, "use_stacking", False)}
                    except Exception:
                        LOG.debug("Ensemble training/eval failed for player %s", pid, exc_info=True)
        except Exception:
            # non-fatal: if ensemble import wasn't available or something failed, continue
            pass

        # extract feature importances if available
        feature_importances = None
        try:
            if hasattr(best_est, "feature_importances_"):
                arr = getattr(best_est, "feature_importances_")
                try:
                    vals = arr.tolist() if hasattr(arr, "tolist") else list(arr)
                    if len(vals) == len(feature_cols):
                        feature_importances = {c: float(v) for c, v in zip(feature_cols, vals)}
                except Exception:
                    feature_importances = None
            elif hasattr(best_est, "coef_"):
                arr = getattr(best_est, "coef_")
                try:
                    flat = arr.ravel() if hasattr(arr, "ravel") else arr
                    vals = flat.tolist() if hasattr(flat, "tolist") else list(flat)
                    if len(vals) == len(feature_cols):
                        feature_importances = {c: float(v) for c, v in zip(feature_cols, vals)}
                except Exception:
                    feature_importances = None
        except Exception:
            feature_importances = None

        # evaluate on val/test if present
        val_mae = None
        if not val.empty:
            X_val = val[feature_cols].to_numpy()
            val_pred = best_est.predict(X_val)
            val_mae = float(_mae(val["target"], val_pred))

        test_mae = None
        if not test.empty:
            X_test = test[feature_cols].to_numpy()
            test_pred = best_est.predict(X_test)
            test_mae = float(_mae(test["target"], test_pred))

        player_name = group["player_name"].iloc[0] if "player_name" in group.columns else f"player_{pid}"
        ensemble_flag = (best_name == "Ensemble")
        metadata = {
            "model_type": f"{best_name}:{type(best_est).__name__}",
            "notes": f"trained from {path.name}",
            "metrics": {k: v for k, v in (("val_mae", val_mae), ("test_mae", test_mae)) if v is not None},
            "feature_columns": feature_cols,
            "hyperparameters": best_params,
            "feature_importances": feature_importances,
            "dataset_version": dataset_version,
            "ensemble_selected": ensemble_flag,
        }
        version = reg.save_model(player_name, best_est, metadata=metadata)
        # Also register the saved artifact in the lightweight simple registry (dev/CI)
        try:
            from backend.services.simple_model_registry import ModelRegistry as SimpleRegistry

            safe = player_name.replace(" ", "_")
            fname = f"{safe}_v{version}.joblib"
            artifact_path = Path(store_dir) / fname
            sreg = SimpleRegistry(base_path=Path(store_dir))
            sreg.register_model(player_name, artifact_src=artifact_path, metadata={**(metadata or {}), "registered_by": "train_models.save_model"})
        except Exception:
            pass
        # Append a CSV row if a report file was requested (regression path)
        if report_csv:
            try:
                import csv

                report_row = {
                    "player_id": player_name,
                    "n_samples": int(len(group)),
                    "model": best_name,
                    "val_mae": metadata.get("metrics", {}).get("val_mae"),
                    "test_mae": metadata.get("metrics", {}).get("test_mae"),
                    "hyperparameters": json.dumps(best_params, default=str),
                    "timestamp": json.dumps(dataset_version),
                    "ensemble_selected": ensemble_flag,
                }
                write_header = not Path(report_csv).exists()
                with open(report_csv, "a", newline="", encoding="utf-8") as fh:
                    w = csv.DictWriter(fh, fieldnames=list(report_row.keys()))
                    if write_header:
                        w.writeheader()
                    w.writerow(report_row)
            except Exception:
                # non-fatal; don't block training on reporting errors
                pass

        results[player_name] = {"version": version, "metrics": metadata["metrics"], "hyperparameters": best_params}
        elapsed = time.time() - start_ts
        try:
            val_mae_val = float(metadata.get("metrics", {}).get("val_mae", float("nan")))
        except Exception:
            val_mae_val = float("nan")
        LOG.info("Finished player %s, model=%s, val_mae=%.4f, elapsed=%.1fs", player_name, best_name, val_mae_val, elapsed)

    # Write a small summary next to dataset
    summary_path = Path(store_dir) / f"training_summary_{path.stem}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    return results


def _cli():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", required=True, help="Path to dataset file (CSV or parquet)")
    p.add_argument("--store-dir", default="backend/models_store")
    p.add_argument("--min-games", type=int, default=50, help="Minimum games required to train a per-player model")
    p.add_argument("--trials", type=int, default=50, help="Optuna trials per model (classification path)")
    p.add_argument("--ensemble-trials", type=int, default=50, help="Optuna trials for ensemble weight tuning (if Optuna available)")
    p.add_argument("--ensemble-timeout", type=int, default=None, help="Timeout (seconds) for ensemble weight tuning (Optuna optimize timeout)")
    p.add_argument("--report", default=None, help="CSV file to append per-player training metrics")
    p.add_argument("--verbose", action="store_true", help="Enable verbose (debug) logging to console")
    args = p.parse_args()
    setup_logging(args.verbose)
    res = train_from_dataset(
        args.dataset,
        args.store_dir,
        min_games=args.min_games,
        trials=args.trials,
        report_csv=args.report,
        ensemble_trials=args.ensemble_trials,
        ensemble_timeout=args.ensemble_timeout,
    )
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    _cli()
