"""Evaluate models matching a filename suffix (e.g., '_abA' or '_abB')."""

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


def find_model_with_suffix(models_dir: Path, player: str, suffix: str):
    safe = re.sub(r"[^a-z0-9]", "_", player.lower())
    # direct pattern
    pats = [f"{player.replace(' ', '_')}{suffix}.pkl", f"{safe}{suffix}.pkl"]
    for pat in pats:
        p = models_dir / pat
        if p.exists():
            return str(p)
    # glob fallback
    for p in models_dir.glob(f"*{suffix}*.pkl"):
        if player.lower() in p.name.lower() or safe in re.sub(
            r"[^a-z0-9]", "_", p.name.lower()
        ):
            return str(p)
    return None


def main(manifest: str, models_dir: str, suffix: str, out_csv: str):
    m = json.loads(Path(manifest).read_text(encoding="utf8"))
    test_p = Path(m["parts"]["test"]["files"]["features"])
    df_test = pd.read_parquet(test_p)
    players = sorted(df_test["player"].unique().tolist())

    rows = []
    models_dir = Path(models_dir)
    for player in players:
        model_path = find_model_with_suffix(models_dir, player, suffix)
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

    write_report(rows, out_csv, None)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument("--models-dir", default="backend/models_store")
    p.add_argument(
        "--suffix",
        required=True,
        help="Suffix string to match in filenames, e.g. '_abA' or '_abB'",
    )
    p.add_argument("--out-csv", default="backend/models_store/eval_suffix.csv")
    args = p.parse_args()
    main(args.manifest, args.models_dir, args.suffix, args.out_csv)
