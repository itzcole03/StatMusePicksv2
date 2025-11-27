#!/usr/bin/env python3
"""Retrain models for players with high binary Brier (>0.20).

- Reads `backend/models_store/calibration_metrics_binary.csv` for brier_cal per player.
- Uses dataset manifest to load train parquet and checks player row counts.
- Trains models via `backend.services.training_pipeline.train_player_model` and saves to `backend/models_store/<player>_retrained.pkl`.
"""
import json
import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "backend" / "models_store"
CALIB_CSV = MODELS_DIR / "calibration_metrics_binary.csv"
MANIFEST = None


def find_manifest():
    p = ROOT / "backend" / "data" / "datasets"
    for d in p.iterdir():
        if not d.is_dir():
            continue
        m = d / "dataset_manifest.json"
        if m.exists():
            return m
    return None


if __name__ == "__main__":
    if not CALIB_CSV.exists():
        logging.error("Calibration CSV not found: %s", CALIB_CSV)
        raise SystemExit(1)
    calib = pd.read_csv(CALIB_CSV)
    # players exceeding threshold
    to_retrain = list(calib[calib["brier_cal"] > 0.20]["player"].tolist())
    if not to_retrain:
        logging.info("No players exceed brier threshold")
        raise SystemExit(0)
    manifest = find_manifest()
    if manifest is None:
        logging.error("No manifest found")
        raise SystemExit(1)
    manifest = json.load(open(manifest))
    train_path = Path(manifest["parts"]["train"]["files"]["features"])
    train_df = pd.read_parquet(train_path)
    logging.info("Loaded train df shape=%s", train_df.shape)

    # ensure repo root on sys.path so backend package imports work
    import sys

    sys.path.insert(0, str(ROOT))
    # import training function
    from backend.services.training_pipeline import save_model, train_player_model

    for player in to_retrain:
        # standardize player name in train_df
        dfp = train_df[train_df["player"] == player]
        if dfp.shape[0] < 50:
            logging.info("Skipping %s: only %d train rows (<50)", player, dfp.shape[0])
            continue
        # prepare features: current train parquet contains only player, game_date, target — attempt to load per-player features from training_data_service
        # fallback: use target as baseline feature
        X = dfp.copy()
        if (
            set(["player", "game_date", "target"]).issuperset(set(dfp.columns))
            and dfp.shape[1] == 3
        ):
            # no extra features — create a simple lag feature
            X = dfp.copy()
            X["lag_1"] = X["target"].shift(1).fillna(X["target"].mean())
            X["lag_3_mean"] = X["target"].rolling(3, min_periods=1).mean()
            X = X.drop(columns=["game_date"])
        else:
            X = dfp.drop(columns=["game_date"])
        # train
        logging.info("Training model for %s on %d rows", player, X.shape[0])
        try:
            model = train_player_model(X, target_col="target")
        except Exception as e:
            logging.exception("Training failed for %s: %s", player, e)
            continue
        out_name = player.replace(" ", "_") + "_retrained.pkl"
        out_path = MODELS_DIR / out_name
        save_model(model, str(out_path))
        logging.info("Saved retrained model to %s", out_path)
    logging.info("Retraining run complete")
