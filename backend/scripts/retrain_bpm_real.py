"""Retrain comparison using real dataset manifest: baseline vs BPM-enhanced.

- Reads `backend/data/datasets/*/dataset_manifest.json` (prefers the most recent points_dataset manifest)
- Loads train features parquet, creates two datasets:
  - baseline: features available in manifest (no multi_BPM)
  - with_bpm: adds `multi_BPM` derived from `multi_PER` as approximation when missing
- Trains VotingRegressor on both and reports CV RMSE.
- Writes report to `backend/models_store/retrain_bpm_real_report.csv` and JSON summary.
"""

from __future__ import annotations

import glob
import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, VotingRegressor
from sklearn.linear_model import ElasticNet
from sklearn.model_selection import cross_val_score

OUT_DIR = os.path.join("backend", "models_store")
os.makedirs(OUT_DIR, exist_ok=True)


def find_latest_points_manifest():
    pattern = os.path.join(
        "backend", "data", "datasets", "points_dataset_*", "dataset_manifest.json"
    )
    files = glob.glob(pattern)
    if not files:
        return None
    # pick latest by filename (contains timestamp)
    files.sort()
    return files[-1]


def load_features_from_manifest(manifest_path):
    with open(manifest_path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    train_info = manifest.get("parts", {}).get("train")
    if not train_info:
        return None
    feat_file = train_info.get("files", {}).get("features")
    if not feat_file or not os.path.exists(feat_file):
        # try relative path
        candidate = os.path.join(os.path.dirname(manifest_path), feat_file or "")
        if os.path.exists(candidate):
            feat_file = candidate
        else:
            return None
    df = pd.read_parquet(feat_file)
    return df


def build_estimator():
    rf = RandomForestRegressor(n_estimators=100, random_state=42)
    en = ElasticNet(alpha=0.1, l1_ratio=0.5, random_state=42)
    return VotingRegressor(estimators=[("rf", rf), ("elastic", en)], weights=[0.6, 0.4])


def evaluate(df, name):
    X = (
        df.drop(columns=["target", "player", "game_date"], errors="ignore")
        .select_dtypes(include=[np.number])
        .fillna(0)
    )
    y = df["target"].astype(float).values
    est = build_estimator()
    scores = cross_val_score(est, X, y, scoring="neg_mean_squared_error", cv=5)
    rmse = float(np.sqrt(-scores.mean()))
    est.fit(X, y)
    path = os.path.join(OUT_DIR, f"retrain_real_{name}.pkl")
    joblib.dump(est, path)
    return rmse, path


def main():
    manifest = find_latest_points_manifest()
    if not manifest:
        print("No points_dataset manifest found under backend/data/datasets. Aborting.")
        return
    print("Using manifest:", manifest)
    df = load_features_from_manifest(manifest)
    if df is None or df.empty:
        print("Failed to load features from manifest. Aborting.")
        return
    print("Loaded features rows:", len(df))

    # baseline: use available numeric features
    baseline_df = df.copy()

    # with BPM: derive multi_BPM if missing
    df_bpm = df.copy()
    if "multi_BPM" not in df_bpm.columns:
        # conservative approximation: (multi_PER - 15) * 0.4
        if "multi_PER" in df_bpm.columns:
            try:
                df_bpm["multi_BPM"] = (df_bpm["multi_PER"].astype(float) - 15.0) * 0.4
            except Exception:
                df_bpm["multi_BPM"] = 0.0
        else:
            df_bpm["multi_BPM"] = 0.0

    # Evaluate
    rmse_base, path_base = evaluate(baseline_df, "baseline_real")
    rmse_bpm, path_bpm = evaluate(df_bpm, "with_bpm_real")

    report = pd.DataFrame(
        [
            {
                "experiment": "baseline_real",
                "rmse_cv": rmse_base,
                "model_path": path_base,
            },
            {
                "experiment": "with_bpm_real",
                "rmse_cv": rmse_bpm,
                "model_path": path_bpm,
            },
        ]
    )
    report_path = os.path.join(OUT_DIR, "retrain_bpm_real_report.csv")
    report.to_csv(report_path, index=False)

    summary = {
        "baseline_rmse": rmse_base,
        "with_bpm_rmse": rmse_bpm,
        "report_csv": report_path,
        "models": [path_base, path_bpm],
        "manifest": manifest,
    }
    with open(
        os.path.join(OUT_DIR, "retrain_bpm_real_summary.json"), "w", encoding="utf-8"
    ) as fh:
        json.dump(summary, fh, indent=2)

    print("Done. Report:", report_path)


if __name__ == "__main__":
    main()
