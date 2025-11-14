r"""Small example script that trains a RandomForestModel on a per-player slice.

Usage (example):
  & .\.venv\Scripts\Activate.ps1
  python -m backend.scripts.example_train_rf --dataset backend/data/test_dataset.csv --min-games 10

This script demonstrates how to use `backend.models.random_forest_model.RandomForestModel`
to train, evaluate, and persist a model for a single player.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from backend.models.random_forest_model import RandomForestModel
from sklearn.metrics import mean_absolute_error, accuracy_score, brier_score_loss, log_loss


def _select_feature_columns(df: pd.DataFrame):
    exclude = {"player_id", "player_name", "target", "split", "game_date"}
    cols = [c for c in df.columns if c not in exclude]
    numeric = df[cols].select_dtypes(include=["number"]).columns.tolist() if cols else []
    return numeric


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", required=True)
    p.add_argument("--player-id", type=int, default=None)
    p.add_argument("--player-name", type=str, default=None)
    p.add_argument("--min-games", type=int, default=50)
    p.add_argument("--store-dir", default="backend/models_store_examples")
    p.add_argument("--n-estimators", type=int, default=100)
    args = p.parse_args()

    path = Path(args.dataset)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    df = pd.read_csv(path) if path.suffix.lower() in (".csv", ".txt") else pd.read_parquet(path)
    if df.empty:
        raise RuntimeError("Empty dataset")

    # find player
    players = list(df.groupby("player_id"))
    chosen = None
    if args.player_id is not None:
        for pid, group in players:
            if int(pid) == int(args.player_id):
                chosen = (pid, group)
                break
    elif args.player_name is not None:
        for pid, group in players:
            if "player_name" in group.columns and group["player_name"].iloc[0] == args.player_name:
                chosen = (pid, group)
                break
    else:
        for pid, group in players:
            if len(group) >= args.min_games:
                chosen = (pid, group)
                break

    if chosen is None:
        raise RuntimeError("No player found meeting criteria (provide --player-id or increase dataset)" )

    pid, group = chosen
    player_name = group["player_name"].iloc[0] if "player_name" in group.columns else f"player_{pid}"
    print(f"Training example for player {player_name} (id={pid}), n={len(group)}")

    # basic split
    if "split" in group.columns:
        train = group[group["split"] == "train"]
        val = group[group["split"] == "val"]
        test = group[group["split"] == "test"]
    else:
        if "game_date" in group.columns:
            g = group.sort_values("game_date")
        else:
            g = group.sample(frac=1.0, random_state=0)
        n = len(g)
        n_train = int(n * 0.7)
        n_val = int(n * 0.15)
        train = g.iloc[:n_train]
        val = g.iloc[n_train : n_train + n_val]
        test = g.iloc[n_train + n_val :]

    feature_cols = _select_feature_columns(group)
    if not feature_cols:
        raise RuntimeError("No numeric feature columns detected for this player")

    X_train = train[feature_cols].to_numpy()
    y_train = train["target"].to_numpy()

    # decide task
    unique_vals = pd.Series(group["target"]).dropna().unique()
    is_binary = len(unique_vals) == 2 and set(map(int, unique_vals)) <= {0, 1} if len(unique_vals) <= 10 else False
    task = "classification" if is_binary else "regression"

    model = RandomForestModel(task=task, n_estimators=args.n_estimators, random_state=0)
    model.train(X_train, y_train, feature_names=feature_cols)

    # eval
    if not val.empty:
        Xv = val[feature_cols].to_numpy()
        yv = val["target"].to_numpy()
        if task == "regression":
            preds = model.predict(Xv)
            val_metric = mean_absolute_error(yv, preds)
            print(f"Val MAE: {val_metric:.6f}")
        else:
            probs = model.predict_proba(Xv)[:, 1]
            preds = (probs >= 0.5).astype(int)
            print(f"Val Brier: {brier_score_loss(yv, probs):.6f}, Val Acc: {accuracy_score(yv, preds):.4f}")

    # persist
    store = Path(args.store_dir)
    store.mkdir(parents=True, exist_ok=True)
    safe = str(player_name).replace(" ", "_")
    outpath = store / f"{safe}_rf_example.joblib"
    model.save(outpath)
    print(f"Saved model to {outpath}")


if __name__ == "__main__":
    main()
