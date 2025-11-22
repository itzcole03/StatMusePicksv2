"""Smoke-train a few per-player models from a dataset manifest.

Reads train/val/test Parquet files referenced by a dataset manifest, builds
simple lag features for each player, trains an ensemble via
`backend.services.training_pipeline.train_player_model`, saves models and
reports per-player MAE on val/test splits.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error

from backend.services.training_pipeline import train_player_model, save_model


def safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


def build_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    # expects df sorted by game_date ascending
    df = df.sort_values("game_date").reset_index(drop=True)
    # simple lag features
    df["lag_1"] = df["target"].shift(1)
    df["lag_3_mean"] = df["target"].shift(1).rolling(window=3, min_periods=1).mean()
    # fallback fills
    df["lag_1"] = df["lag_1"].fillna(df["target"].mean())
    df["lag_3_mean"] = df["lag_3_mean"].fillna(df["target"].mean())
    return df


def load_splits(manifest_path: Path) -> dict:
    with open(manifest_path, "r", encoding="utf8") as fh:
        m = json.load(fh)

    parts = {}
    for split in ("train", "val", "test"):
        p = m["parts"][split]
        fp = Path(p["files"]["features"])
        if not fp.exists():
            raise FileNotFoundError(f"Features file not found: {fp}")
        df = pd.read_parquet(fp)
        df = df.copy()
        # ensure game_date is datetime
        df["game_date"] = pd.to_datetime(df["game_date"]).dt.tz_localize(None)
        df["_split"] = split
        parts[split] = df
    return parts


def main(manifest: str, n_players: int, out_dir: str):
    manifest_path = Path(manifest)
    parts = load_splits(manifest_path)
    combined = pd.concat([parts["train"], parts["val"], parts["test"]], ignore_index=True)

    players = combined["player"].unique().tolist()
    players = players[:n_players]

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = []
    for player in players:
        player_df = combined[combined["player"] == player].copy()
        if player_df.shape[0] < 12:
            print(f"Skipping {player}: too few rows ({player_df.shape[0]})")
            continue

        player_df = build_lag_features(player_df)

        # split back
        train_df = player_df[player_df["_split"] == "train"].drop(columns=["_split"]).copy()
        val_df = player_df[player_df["_split"] == "val"].drop(columns=["_split"]).copy()
        test_df = player_df[player_df["_split"] == "test"].drop(columns=["_split"]).copy()

        if train_df.shape[0] < 8:
            print(f"Skipping {player}: not enough training rows ({train_df.shape[0]})")
            continue

        feat_cols = ["lag_1", "lag_3_mean"]

        # ensure columns present
        for c in feat_cols:
            if c not in train_df.columns:
                train_df[c] = 0.0
                val_df[c] = 0.0
                test_df[c] = 0.0

        train_for_model = train_df[feat_cols + ["target"]].reset_index(drop=True)
        model = train_player_model(train_for_model, target_col="target")

        model_path = out_dir / f"{safe_name(player)}.pkl"
        save_model(model, str(model_path))

        # Evaluate
        def predict_df(m, df):
            if df.shape[0] == 0:
                return np.array([])
            X = df[feat_cols].select_dtypes(include=[np.number]).fillna(0)
            try:
                return m.predict(X)
            except Exception:
                return np.zeros(len(df))

        y_val = val_df["target"].values if val_df.shape[0] > 0 else np.array([])
        y_test = test_df["target"].values if test_df.shape[0] > 0 else np.array([])

        yval_pred = predict_df(model, val_df)
        ytest_pred = predict_df(model, test_df)

        val_mae = float(mean_absolute_error(y_val, yval_pred)) if y_val.size and yval_pred.size else None
        test_mae = float(mean_absolute_error(y_test, ytest_pred)) if y_test.size and ytest_pred.size else None

        print(f"Player: {player} train_rows={train_df.shape[0]} val_rows={val_df.shape[0]} test_rows={test_df.shape[0]} val_mae={val_mae} test_mae={test_mae}")
        summary.append({"player": player, "val_mae": val_mae, "test_mae": test_mae, "model_path": str(model_path)})

    out_sum = manifest_path.parent / "smoke_train_summary.json"
    with open(out_sum, "w", encoding="utf8") as fh:
        json.dump(summary, fh, indent=2)
    print("Wrote summary to", out_sum)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, help="Path to dataset manifest.json")
    parser.add_argument("--players", type=int, default=5, help="Number of players to train")
    parser.add_argument("--out-dir", default="backend/models_store/smoke", help="Directory to save models")
    args = parser.parse_args()
    main(args.manifest, args.players, args.out_dir)
