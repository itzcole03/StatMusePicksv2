"""Runner script: evaluate saved models against manifest test splits.

Writes a CSV summarizing per-player metrics for models found in `models_dir`.
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

import re

import pandas as pd

from backend.services.eval_report import (
    evaluate_model_on_df,
    load_model_if_exists,
    write_report,
)


def load_manifest(manifest_path: Path) -> dict:
    with open(manifest_path, "r", encoding="utf8") as fh:
        return json.load(fh)


def find_model_file(models_dir: Path, player: str):
    # prefer exact match or *_advanced variants, then fuzzy matches
    def _safe(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "_", s.lower())

    player_safe = _safe(player)
    # ordered patterns to prefer advanced / explicit files
    patterns = [
        f"{player}.pkl",
        f"{player}_advanced*.pkl",
        f"{player}_*.pkl",
        f"{player}*.pkl",
        f"{player_safe}.pkl",
        f"{player_safe}_advanced*.pkl",
        f"{player_safe}_*.pkl",
        f"{player_safe}*.pkl",
    ]
    for pat in patterns:
        matches = list(models_dir.glob(pat))
        if matches:
            return str(matches[0])

    # final fallback: fuzzy case-insensitive containment on normalized names
    for p in models_dir.glob("*.pkl"):
        fname = p.name
        if player.lower() in fname.lower():
            return str(p)
        if player_safe in _safe(fname):
            return str(p)
    return None


def main(manifest: str, models_dir: str, out_csv: str, out_json: str | None = None):
    m = load_manifest(Path(manifest))
    test_p = Path(m["parts"]["test"]["files"]["features"])
    df_test = pd.read_parquet(test_p)
    players = sorted(df_test["player"].unique().tolist())

    rows = []
    models_dir = Path(models_dir)
    for player in players:
        model_path = find_model_file(models_dir, player)
        if not model_path:
            rows.append(
                {"player": player, "status": "missing_model", "model_path": None}
            )
            continue
        model = load_model_if_exists(model_path)
        if model is None:
            rows.append(
                {"player": player, "status": "load_failed", "model_path": model_path}
            )
            continue

        player_df = df_test[df_test["player"] == player].copy()
        # try to infer feature columns (exclude game_date, player, target)
        exclude = set(["game_date", "player", "target"])
        feature_cols = [c for c in player_df.columns if c not in exclude]
        if len(feature_cols) == 0:
            rows.append(
                {"player": player, "status": "no_features", "model_path": model_path}
            )
            continue

        eval_res = evaluate_model_on_df(model, player_df, feature_cols)
        if "metrics" in eval_res:
            r = {"player": player, "status": "ok", "model_path": model_path}
            r.update(eval_res["metrics"])
            rows.append(r)
        else:
            rows.append(
                {
                    "player": player,
                    "status": "error",
                    "error": eval_res.get("error"),
                    "model_path": model_path,
                }
            )

    write_report(rows, out_csv, out_json)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument("--models-dir", required=True)
    p.add_argument("--out-csv", default="backend/models_store/eval_report.csv")
    p.add_argument("--out-json", default=None)
    args = p.parse_args()
    main(args.manifest, args.models_dir, args.out_csv, args.out_json)
