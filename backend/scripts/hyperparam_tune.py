"""Per-player hyperparameter tuning harness using existing tuning functions.

Writes a CSV of best params per player.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd

from backend.services.training_pipeline import (
    tune_random_forest_hyperparams,
    tune_xgboost_hyperparams,
)


def load_manifest(manifest_path: Path) -> dict:
    with open(manifest_path, "r", encoding="utf8") as fh:
        return json.load(fh)


def main(
    manifest: str,
    out_csv: str,
    min_games: int = 50,
    n_trials: int = 20,
    limit: int | None = None,
):
    m = load_manifest(Path(manifest))
    parts = {}
    for split in ("train", "val", "test"):
        p = m["parts"][split]
        parts[split] = pd.read_parquet(Path(p["files"]["features"]))

    combined = pd.concat(
        [parts["train"], parts["val"], parts["test"]], ignore_index=True
    )
    counts = combined.groupby("player").size().sort_values(ascending=False)
    candidates = counts[counts >= min_games].index.tolist()
    if limit is not None:
        candidates = candidates[:limit]

    rows = []
    for player in candidates:
        try:
            df_train = parts["train"][parts["train"]["player"] == player].copy()
            df_val = parts["val"][parts["val"]["player"] == player].copy()
            tune_df = (
                pd.concat([df_train, df_val], ignore_index=True)
                if df_val.shape[0] > 0
                else df_train
            )
            if tune_df.shape[0] < 3:
                rows.append(
                    {"player": player, "status": "skipped", "reason": "too few rows"}
                )
                continue
            # ensure target present
            if "target" not in tune_df.columns:
                rows.append(
                    {"player": player, "status": "skipped", "reason": "no target"}
                )
                continue

            try:
                best_rf = tune_random_forest_hyperparams(
                    tune_df[["target"] + [c for c in tune_df.columns if c != "target"]],
                    target_col="target",
                    n_trials=n_trials,
                )
            except Exception as e:
                best_rf = {"error": str(e)}

            try:
                best_xgb = tune_xgboost_hyperparams(
                    tune_df[["target"] + [c for c in tune_df.columns if c != "target"]],
                    target_col="target",
                    n_trials=n_trials,
                )
            except Exception as e:
                best_xgb = {"error": str(e)}

            rows.append(
                {
                    "player": player,
                    "status": "ok",
                    "best_rf": json.dumps(best_rf),
                    "best_xgb": json.dumps(best_xgb),
                }
            )
        except Exception as exc:
            rows.append({"player": player, "status": "failed", "error": str(exc)})

    # write CSV
    with open(out_csv, "w", newline="", encoding="utf8") as fh:
        fieldnames = ["player", "status", "best_rf", "best_xgb", "reason", "error"]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k) for k in fieldnames})


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True, help="Path to dataset manifest.json")
    p.add_argument(
        "--out-csv", default="backend/models_store/hyperparam_tune_report.csv"
    )
    p.add_argument("--min-games", type=int, default=50)
    p.add_argument("--n-trials", type=int, default=20)
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()
    main(
        args.manifest,
        args.out_csv,
        min_games=args.min_games,
        n_trials=args.n_trials,
        limit=args.limit,
    )
