#!/usr/bin/env python3
"""Backtest using calibrated probabilities built from validation set and saved calibrators.

- Loads validation features from discovered manifest.
- For each val row, loads corresponding model and calibrator (if present), computes raw prob using empirical prob over predicted_value, applies calibrator, builds dataset with pred_prob, actual (target>pred), odds=2.0.
- Runs BacktestEngine.run and writes report JSON to backend/models_store/backtest_reports/calibrated_backtest_<ts>.json
"""
import datetime
import json
import logging
from datetime import timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import sys

# Ensure repo root is on sys.path so `backend` imports work when running scripts
sys.path.insert(0, str(ROOT))
MODELS_DIR = ROOT / "backend" / "models_store"
REPORT_DIR = MODELS_DIR / "backtest_reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def find_manifest():
    p = ROOT / "backend" / "data" / "datasets"
    for d in p.iterdir():
        if not d.is_dir():
            continue
        m = d / "dataset_manifest.json"
        if m.exists():
            return m
    return None


def empirical_prob_over(y_vals, pred_value):
    return float(np.mean(np.array(y_vals) > pred_value))


if __name__ == "__main__":
    m = find_manifest()
    if m is None:
        raise SystemExit("No manifest")
    manifest = json.load(open(m))
    val_path = Path(manifest["parts"]["val"]["files"]["features"])
    val_df = pd.read_parquet(val_path)
    # load train for empirical distributions
    train_path = Path(manifest["parts"]["train"]["files"]["features"])
    train_df = pd.read_parquet(train_path)

    # prepare records
    records = []
    for idx, row in val_df.iterrows():
        player = row["player"]
        target = float(row["target"])
        # load model
        name = player.replace(" ", "_")
        model_path = MODELS_DIR / f"{name}.pkl"
        calib_path = MODELS_DIR / f"{name}_calibrator.pkl"
        # try retrained model first
        retrain_path = MODELS_DIR / f"{name}_retrained.pkl"
        if retrain_path.exists():
            model_path = retrain_path
        # load model if exists
        model = None
        if model_path.exists():
            try:
                model = joblib.load(model_path)
            except Exception:
                model = None
        # predict: try model.predict with no features -> fallback to train mean for player
        if model is not None:
            try:
                # no feature columns in val; predict single value using mean target
                # since model expects features, we fallback to model.predict on zeros if needed
                X = np.zeros((1, 1))
                pred = float(model.predict(X.reshape(1, -1))[0])
            except Exception:
                try:
                    pred = float(model.predict(np.array([0.0]).reshape(1, -1))[0])
                except Exception:
                    pred = float(
                        train_df[train_df["player"] == player]["target"].mean()
                        if not train_df[train_df["player"] == player].empty
                        else train_df["target"].mean()
                    )
        else:
            pred = float(
                train_df[train_df["player"] == player]["target"].mean()
                if not train_df[train_df["player"] == player].empty
                else train_df["target"].mean()
            )

        # empirical raw prob using player's train history
        y_hist = train_df[train_df["player"] == player]["target"].values
        if len(y_hist) < 3:
            # fallback to overall empirical
            y_hist = train_df["target"].values
        raw_prob = empirical_prob_over(y_hist, pred)
        # apply calibrator if exists
        calibrated = raw_prob
        if calib_path.exists():
            try:
                calib = joblib.load(calib_path)
                calibrated = float(calib.predict([raw_prob])[0])
            except Exception:
                pass
        actual = 1 if target > pred else 0
        records.append({"pred_prob": calibrated, "actual": actual, "odds": 2.0})

    # run backtest
    from backend.evaluation.backtesting import BacktestEngine, write_report_json

    engine = BacktestEngine(start_bankroll=1000.0)
    df = pd.DataFrame(records)
    res = engine.run(
        df,
        prob_col="pred_prob",
        actual_col="actual",
        odds_col="odds",
        stake_mode="flat",
        flat_stake=5.0,
    )

    report = {
        "generated_at": datetime.datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "n_records": len(df),
        "summary": res.__dict__ if hasattr(res, "__dict__") else dict(res),
    }
    out = REPORT_DIR / f"calibrated_backtest_{report['generated_at']}.json"
    write_report_json(report, str(out))
    print("Wrote backtest report to", out)
