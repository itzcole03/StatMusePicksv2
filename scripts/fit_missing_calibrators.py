"""Fit and persist calibrators for models that lack them.

Usage: python scripts/fit_missing_calibrators.py --manifest <manifest.json> --models-dir <models_dir>

Scans models in `models_dir`, for each model without an existing calibrator:
- loads the validation set from the manifest for that player
- predicts with the model on validation features
- fits an isotonic calibrator and persists it via `CalibrationService`
- appends per-player calibration metrics to a JSON report
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

import os
import sys

# Ensure repo root is on sys.path so `backend` imports work when run as script
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.services.model_registry import ModelRegistry
from backend.services.calibration_service import CalibrationService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("fit_calibrators")


def load_manifest(manifest_path: Path) -> dict:
    with open(manifest_path, "r", encoding="utf8") as fh:
        return json.load(fh)


def read_features(parquet_path: Path) -> pd.DataFrame:
    df = pd.read_parquet(parquet_path)
    df = df.copy()
    df["game_date"] = pd.to_datetime(df["game_date"]).dt.tz_localize(None)
    return df


def main(manifest: str, models_dir: str, out_report: str | None = None):
    manifest_path = Path(manifest)
    m = load_manifest(manifest_path)

    parts = {}
    for split in ("train", "val", "test"):
        p = m["parts"][split]
        parts[split] = read_features(Path(p["files"]["features"]))

    registry = ModelRegistry(model_dir=models_dir)
    calib_service = CalibrationService(model_dir=models_dir)

    report = []

    for fname in registry.list_models():
        player = fname[:-4].replace("_", " ")
        try:
            # skip if calibrator exists
            if registry.load_calibrator(player) is not None:
                log.info("Calibrator exists for %s, skipping", player)
                continue

            # ensure validation data exists for player
            val_df = parts["val"][parts["val"]["player"] == player].copy()
            if val_df.shape[0] < 3:
                log.info("Not enough val rows for %s (%d), skipping", player, val_df.shape[0])
                report.append({"player": player, "status": "skip_no_val", "val_rows": int(val_df.shape[0])})
                continue

            # ensure validation features exist; use the same numeric feature columns
            val_df = val_df.sort_values("game_date").reset_index(drop=True)
            # derive simple lag features if missing (safe to add)
            if "lag_1" not in val_df.columns:
                val_df["lag_1"] = val_df["target"].shift(1).fillna(val_df["target"].mean())
            if "lag_3_mean" not in val_df.columns:
                val_df["lag_3_mean"] = val_df["target"].shift(1).rolling(window=3, min_periods=1).mean().fillna(val_df["target"].mean())

            model = registry.load_model(player)
            if model is None:
                log.info("Model not found for %s, skipping", player)
                report.append({"player": player, "status": "no_model"})
                continue

            # Build X_val using all numeric columns that are likely model features,
            # excluding identifiers and the target.
            drop_cols = {"player", "target", "game_date", "game_id", "season"}
            numeric_cols = [c for c in val_df.select_dtypes(include=[np.number]).columns if c not in drop_cols]
            if not numeric_cols:
                log.info("No numeric features found for %s, skipping", player)
                report.append({"player": player, "status": "no_numeric_features"})
                continue

            X_val = val_df[numeric_cols].fillna(0)
            # Align features to the model's expected inputs when possible.
            expected = None
            try:
                if hasattr(model, "feature_names_in_"):
                    expected = list(model.feature_names_in_)
                else:
                    # Try ensemble estimators
                    if hasattr(model, "estimators_") and len(model.estimators_) > 0:
                        est = model.estimators_[0]
                        if hasattr(est, "feature_names_in_"):
                            expected = list(est.feature_names_in_)
            except Exception:
                expected = None

            if expected:
                # build X2 with expected column order, filling missing with zeros
                import pandas as _pd

                X2 = _pd.DataFrame(index=X_val.index)
                for c in expected:
                    if c in X_val.columns:
                        X2[c] = X_val[c]
                    else:
                        X2[c] = 0.0
                try:
                    y_pred = model.predict(X2)
                except Exception:
                    y_pred = model.predict(X2.values)
            else:
                # fallback: try predicting with X_val directly; if shape mismatch, try padding
                try:
                    y_pred = model.predict(X_val)
                except Exception:
                    try:
                        y_pred = model.predict(X_val.values)
                    except Exception:
                        # If model expects more features, pad zeros to match n_features_in_
                        n_expected = getattr(model, "n_features_in_", None)
                        if n_expected and X_val.shape[1] < n_expected:
                            import numpy as _np
                            pad = _np.zeros((X_val.shape[0], n_expected - X_val.shape[1]))
                            try:
                                y_pred = model.predict(_np.hstack([X_val.values, pad]))
                            except Exception:
                                raise
                        else:
                            raise

            y_true = val_df["target"].astype(float).to_numpy()

            # fit and persist calibrator
            try:
                info = calib_service.fit_and_save(player, y_true=y_true, y_pred=y_pred, method="isotonic")
                log.info("Fitted calibrator for %s: %s", player, info.get("method"))
                report.append({"player": player, "status": "fitted", "metrics": info})
            except Exception as e:
                log.exception("Failed to fit calibrator for %s", player)
                report.append({"player": player, "status": "failed", "error": str(e)})

        except Exception as e:
            log.exception("Unexpected error for %s", player)
            report.append({"player": player, "status": "error", "error": str(e)})

    if out_report:
        with open(out_report, "w", encoding="utf8") as fh:
            json.dump(report, fh, indent=2)
        log.info("Wrote calibrator report to %s", out_report)
    else:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument("--models-dir", required=True)
    p.add_argument("--out-report", required=False)
    args = p.parse_args()
    main(args.manifest, args.models_dir, args.out_report)
