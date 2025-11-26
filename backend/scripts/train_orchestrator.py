"""Orchestrate training of per-player models from a dataset manifest.

Reads train/val/test Parquet files listed in a manifest, selects players
with at least `min_games` total rows, trains per-player models using
`backend.services.training_pipeline.train_player_model`, saves models via
`ModelRegistry`, and writes a CSV training report.

This is intentionally simple and synchronous; it can be extended to run
in parallel or scheduled via CI/cron as the roadmap requires.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import math
from pathlib import Path
import os
import sys

# Ensure repo root is on sys.path so `backend` imports work when run as script
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np
import pandas as pd

from backend.services.training_pipeline import train_player_model
from backend.services.model_registry import ModelRegistry

import multiprocessing
from typing import Optional


def _train_worker(kwargs: dict) -> dict:
    """Top-level worker function for multiprocessing. Receives a kwargs dict
    so it's pickle-friendly on Windows.
    """
    manifest = kwargs["manifest"]
    player = kwargs["player"]
    out_dir = kwargs["out_dir"]
    fit_calibrator = kwargs.get("fit_calibrator", False)

    try:
        # local imports inside worker
        from backend.services.model_registry import ModelRegistry
        from backend.services import calibration_service as calib_mod
        import joblib

        m_path = Path(manifest)
        with open(m_path, "r", encoding="utf8") as fh:
            mm = json.load(fh)

        # load parts just for this player
        parts = {}
        for split in ("train", "val", "test"):
            p = mm["parts"][split]
            fp = Path(p["files"]["features"])
            df = pd.read_parquet(fp)
            df = df.copy()
            df["game_date"] = pd.to_datetime(df["game_date"]).dt.tz_localize(None)
            parts[split] = df

        train_df = parts["train"][parts["train"]["player"] == player].copy()
        val_df = parts["val"][parts["val"]["player"] == player].copy()
        test_df = parts["test"][parts["test"]["player"] == player].copy()

        if train_df.shape[0] < 1:
            return {"player": player, "status": "skipped", "reason": "no train rows"}

        # build simple lag features
        train_df = build_lag_features(train_df)
        val_df = build_lag_features(val_df) if val_df.shape[0] > 0 else val_df
        test_df = build_lag_features(test_df) if test_df.shape[0] > 0 else test_df

        feat_cols = ["lag_1", "lag_3_mean"]
        for c in feat_cols:
            for df in (train_df, val_df, test_df):
                if c not in df.columns:
                    df[c] = 0.0

        train_for_model = train_df[feat_cols + ["target"]].reset_index(drop=True)
        # Optional feature selection prior to training
        if kwargs.get("feature_selection", False):
            try:
                from backend.services.feature_selection import (
                    select_by_correlation,
                    rfe_select,
                )

                # run a lightweight correlation filter first
                sel_corr = select_by_correlation(
                    train_for_model, target_col="target", thresh=0.01
                )
                if len(sel_corr) >= 3:
                    # retain a small core set; then run RFE to choose final features
                    reduced = train_for_model[sel_corr + ["target"]].copy()
                    chosen = rfe_select(
                        reduced,
                        target_col="target",
                        n_features=min(6, max(1, len(sel_corr) // 2)),
                    )
                else:
                    # fallback: run RFE on full feature set
                    chosen = rfe_select(
                        train_for_model,
                        target_col="target",
                        n_features=min(6, max(1, train_for_model.shape[1] // 2)),
                    )
                if chosen and len(chosen) > 0:
                    # ensure target present
                    train_for_model = train_for_model[chosen + ["target"]].reset_index(
                        drop=True
                    )
                    # persist chosen feature list next to model later in worker
                    kwargs["_selected_features"] = chosen
            except Exception:
                # if feature-selection fails, continue with default features
                pass
        # optional hyperparameter tuning for RandomForest component
        tune_info = None
        if kwargs.get("tune", False):
            try:
                from backend.services.training_pipeline import (
                    tune_random_forest_hyperparams,
                )

                # use train + val where available for tuning
                tune_df = (
                    pd.concat([train_df, val_df], ignore_index=True)
                    if val_df.shape[0] > 0
                    else train_df
                )
                tune_df = (
                    build_lag_features(tune_df) if tune_df.shape[0] > 0 else tune_df
                )
                # ensure required feature columns exist
                for c in feat_cols:
                    if c not in tune_df.columns:
                        tune_df[c] = 0.0
                tune_df_for = tune_df[feat_cols + ["target"]].reset_index(drop=True)
                n_trials = int(kwargs.get("tune_trials", 20))
                best = tune_random_forest_hyperparams(
                    tune_df_for, target_col="target", n_trials=n_trials
                )
                tune_info = {"best_params": best, "n_trials": n_trials}
                # persist best params to disk next to models
                params_path = Path(out_dir) / f"{player}_best_rf_params.json"
                with open(params_path, "w", encoding="utf8") as pf:
                    json.dump(
                        {"player": player, "best_params": best, "n_trials": n_trials},
                        pf,
                    )
            except Exception:
                tune_info = None

        model = train_player_model(train_for_model, target_col="target")

        registry = ModelRegistry(model_dir=str(out_dir))
        registry.save_model(player, model, version=None, notes="orchestrator-parallel")

        # persist selected features list if present
        try:
            sel = kwargs.get("_selected_features")
            if sel:
                feat_path = Path(out_dir) / f"{player}_selected_features.json"
                with open(feat_path, "w", encoding="utf8") as fh:
                    json.dump({"player": player, "selected_features": sel}, fh)
        except Exception:
            pass

        # optionally fit calibrator
        if fit_calibrator and val_df.shape[0] >= 3:
            try:
                # ensure calibrator is saved to the same model_dir used by the orchestrator
                calib = calib_mod.CalibrationService(model_dir=str(out_dir))
                # assemble validation features and align to model's expected feature names
                X_val = val_df[feat_cols].copy()
                # attempt to reorder/add missing cols according to model.feature_names_in_
                try:
                    if hasattr(model, "_feature_list") and getattr(
                        model, "_feature_list", None
                    ):
                        expected = list(getattr(model, "_feature_list"))
                        # ensure missing columns are added and columns are ordered
                        for c in expected:
                            if c not in X_val.columns:
                                X_val[c] = 0.0
                        X_val = X_val.reindex(columns=expected)
                    elif hasattr(model, "feature_names_in_"):
                        expected = list(model.feature_names_in_)
                        for c in expected:
                            if c not in X_val.columns:
                                X_val[c] = 0.0
                        X_val = X_val.reindex(columns=expected)
                    elif hasattr(model, "estimators_") and len(model.estimators_) > 0:
                        est = model.estimators_[0]
                        if hasattr(est, "feature_names_in_"):
                            expected = list(est.feature_names_in_)
                            for c in expected:
                                if c not in X_val.columns:
                                    X_val[c] = 0.0
                            X_val = X_val.reindex(columns=expected)
                except Exception:
                    # if alignment fails, fall back to numeric subset
                    X_val = X_val.select_dtypes(include=["number"]).fillna(0)

                X_val = X_val.select_dtypes(include=["number"]).fillna(0)
                y_val = val_df["target"].astype(float).to_numpy()
                try:
                    y_pred_val = model.predict(X_val)
                except Exception:
                    y_pred_val = model.predict(X_val.values)
                cal_info = calib.fit_and_save(
                    player, y_true=y_val, y_pred=y_pred_val, method="isotonic"
                )
            except Exception:
                cal_info = None
        else:
            cal_info = None

        return {
            "player": player,
            "status": "trained",
            "train_rows": int(train_df.shape[0]),
            "val_rows": int(val_df.shape[0]) if hasattr(val_df, "shape") else 0,
            "test_rows": int(test_df.shape[0]) if hasattr(test_df, "shape") else 0,
            "val_mae": None,
            "test_mae": None,
            "model_path": registry._model_path(player),
            "cal_info": cal_info,
            "tune_info": tune_info,
        }
    except Exception as e:
        return {"player": player, "status": "failed", "error": str(e)}


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def load_manifest(manifest_path: Path) -> dict:
    with open(manifest_path, "r", encoding="utf8") as fh:
        return json.load(fh)


def read_features(parquet_path: Path) -> pd.DataFrame:
    df = pd.read_parquet(parquet_path)
    df = df.copy()
    df["game_date"] = pd.to_datetime(df["game_date"]).dt.tz_localize(None)
    return df


def build_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("game_date").reset_index(drop=True)
    df["lag_1"] = df["target"].shift(1)
    df["lag_3_mean"] = df["target"].shift(1).rolling(window=3, min_periods=1).mean()
    df["lag_1"] = df["lag_1"].fillna(df["target"].mean())
    df["lag_3_mean"] = df["lag_3_mean"].fillna(df["target"].mean())
    return df


def main(
    manifest: str,
    min_games: int,
    out_dir: str,
    report_csv: str,
    limit: int | None,
    workers: int = 1,
    fit_calibrators: bool = False,
    tune: bool = False,
    tune_trials: int = 20,
    feature_selection: bool = False,
):
    manifest_path = Path(manifest)
    m = load_manifest(manifest_path)

    parts = {}
    for split in ("train", "val", "test"):
        p = m["parts"][split]
        fp = Path(p["files"]["features"])
        parts[split] = read_features(fp)

    combined = pd.concat(
        [parts["train"], parts["val"], parts["test"]], ignore_index=True
    )

    counts = combined.groupby("player").size().sort_values(ascending=False)
    candidates = counts[counts >= min_games].index.tolist()

    if limit is not None:
        candidates = candidates[:limit]

    logger.info(
        "Found %d players with >= %d rows (using limit=%s)",
        len(candidates),
        min_games,
        limit,
    )

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    registry = ModelRegistry(model_dir=str(out_dir))

    # prepare worker kwargs
    worker_kwargs = []
    for player in candidates:
        worker_kwargs.append(
            {
                "manifest": str(manifest_path),
                "player": player,
                "out_dir": str(out_dir),
                "fit_calibrator": bool(fit_calibrators),
                "tune": bool(tune),
                "tune_trials": int(tune_trials),
                "feature_selection": bool(feature_selection),
            }
        )

    report_rows = []
    if workers is None or workers <= 1:
        logger.info("Running training serially for %d players", len(worker_kwargs))
        for kw in worker_kwargs:
            r = _train_worker(kw)
            if r:
                report_rows.append(
                    {
                        "player": r.get("player"),
                        "train_rows": r.get("train_rows", 0),
                        "val_rows": r.get("val_rows", 0),
                        "test_rows": r.get("test_rows", 0),
                        "val_mae": r.get("val_mae"),
                        "test_mae": r.get("test_mae"),
                        "model_path": r.get("model_path"),
                    }
                )
    else:
        logger.info("Starting parallel training with %d workers", workers)
        with multiprocessing.Pool(processes=workers) as pool:
            for r in pool.imap_unordered(_train_worker, worker_kwargs):
                if r:
                    report_rows.append(
                        {
                            "player": r.get("player"),
                            "train_rows": r.get("train_rows", 0),
                            "val_rows": r.get("val_rows", 0),
                            "test_rows": r.get("test_rows", 0),
                            "val_mae": r.get("val_mae"),
                            "test_mae": r.get("test_mae"),
                            "model_path": r.get("model_path"),
                        }
                    )

    # Write report CSV
    csv_path = Path(report_csv)
    with open(csv_path, "w", newline="", encoding="utf8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "player",
                "train_rows",
                "val_rows",
                "test_rows",
                "val_mae",
                "test_mae",
                "model_path",
            ],
        )
        writer.writeheader()
        for r in report_rows:
            writer.writerow(r)

    logger.info("Wrote training report to %s", csv_path)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True, help="Path to dataset manifest.json")
    p.add_argument(
        "--min-games",
        type=int,
        default=50,
        help="Minimum total rows for a player to train",
    )
    p.add_argument(
        "--out-dir", default="backend/models_store", help="Directory to save models"
    )
    p.add_argument(
        "--report-csv",
        default="backend/models_store/training_report.csv",
        help="CSV report path",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of players to train (for smoke)",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel worker processes to use",
    )
    p.add_argument(
        "--fit-calibrators",
        action="store_true",
        help="Fit calibrators from validation set when available",
    )
    p.add_argument(
        "--tune",
        action="store_true",
        help="Run RF hyperparameter tuning per-player before training and persist best params",
    )
    p.add_argument(
        "--tune-trials",
        type=int,
        default=20,
        help="Number of Optuna trials to run when --tune is set",
    )
    p.add_argument(
        "--feature-selection",
        action="store_true",
        help="Run feature selection (correlation + RFE) before training",
    )
    args = p.parse_args()
    main(
        args.manifest,
        args.min_games,
        args.out_dir,
        args.report_csv,
        args.limit,
        workers=args.workers,
        fit_calibrators=args.fit_calibrators,
        tune=args.tune,
        tune_trials=args.tune_trials,
        feature_selection=args.feature_selection,
    )
