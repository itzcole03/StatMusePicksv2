"""Grid-search ensemble weight optimizer.

For each player in the manifest, uses train+val parts to search simple weight
combinations for the VotingRegressor to minimize validation RMSE. Writes CSV
with best weights per player.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error

from backend.services.training_pipeline import build_ensemble_with_weights


def load_manifest(manifest_path: Path) -> dict:
    with open(manifest_path, "r", encoding="utf8") as fh:
        return json.load(fh)


def evaluate_weights_on_player(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    feat_cols: list,
    weights_grid: list[list[float]],
):
    # train ensemble per weight candidate on train_df and evaluate on val_df
    X_train = train_df[feat_cols].select_dtypes(include=[np.number]).fillna(0)
    y_train = train_df["target"].astype(float).to_numpy()
    X_val = val_df[feat_cols].select_dtypes(include=[np.number]).fillna(0)
    y_val = val_df["target"].astype(float).to_numpy()

    best = None
    best_rmse = float("inf")
    for w in weights_grid:
        try:
            model = build_ensemble_with_weights(w)
            model.fit(X_train, y_train)
            preds = model.predict(X_val)
            rmse = float(np.sqrt(mean_squared_error(y_val, preds)))
            if rmse < best_rmse:
                best_rmse = rmse
                best = {"weights": w, "rmse": rmse}
        except Exception:
            continue
    return best


def generate_weight_grid(n_estimators=3, step=0.25):
    # produce weight combinations for up to 3 estimators that sum to 1 within tolerance
    vals = [i * step for i in range(int(1 / step) + 1)]
    combos = []
    for a in vals:
        for b in vals:
            for c in vals:
                s = a + b + c
                if abs(s - 1.0) <= 1e-6:
                    combos.append([a, b, c])
    return combos


def main(manifest: str, out_csv: str, limit: int | None = None):
    m = load_manifest(Path(manifest))
    parts = {}
    for split in ("train", "val", "test"):
        p = m["parts"][split]
        parts[split] = pd.read_parquet(Path(p["files"]["features"]))

    combined = pd.concat(
        [parts["train"], parts["val"], parts["test"]], ignore_index=True
    )
    counts = combined.groupby("player").size().sort_values(ascending=False)
    candidates = counts.index.tolist()
    if limit is not None:
        candidates = candidates[:limit]

    grid = generate_weight_grid(step=0.25)
    rows = []
    for player in candidates:
        train_df = parts["train"][parts["train"]["player"] == player].copy()
        val_df = parts["val"][parts["val"]["player"] == player].copy()
        if train_df.shape[0] < 5 or val_df.shape[0] < 3:
            rows.append(
                {"player": player, "status": "skipped", "reason": "insufficient_rows"}
            )
            continue

        exclude = set(["game_date", "player", "target"])
        feat_cols = [c for c in train_df.columns if c not in exclude]
        if len(feat_cols) == 0:
            rows.append(
                {"player": player, "status": "skipped", "reason": "no_features"}
            )
            continue

        best = evaluate_weights_on_player(train_df, val_df, feat_cols, grid)
        if best is None:
            rows.append(
                {"player": player, "status": "failed", "reason": "no_candidate"}
            )
        else:
            rows.append(
                {
                    "player": player,
                    "status": "ok",
                    "best_weights": json.dumps(best["weights"]),
                    "val_rmse": float(best["rmse"]),
                }
            )

    df = pd.DataFrame(rows)
    df.to_csv(out_csv, index=False)
    print("Wrote ensemble optimize report to", out_csv)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument(
        "--out-csv", default="backend/models_store/ensemble_weights_report.csv"
    )
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()
    main(args.manifest, args.out_csv, limit=args.limit)
