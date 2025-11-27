"""Estimate simple ROI for using LLM features per-player.

This tool compares evaluation CSVs for A (with LLM) and B (no LLM) and
computes delta metrics and an estimated LLM cost per player given a
`LLM_COST_PER_CALL` and `LLM_CALLS_PER_PLAYER` environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd


def main(eval_a: str, eval_b: str, out_csv: str | None = None):
    da = pd.read_csv(eval_a)
    db = pd.read_csv(eval_b)
    merged = da.merge(db, on="player", suffixes=("_a", "_b"))
    merged["delta_rmse"] = (
        merged["val_rmse_b"] - merged["val_rmse_a"]
        if "val_rmse_a" in merged.columns
        else merged.get("rmse_b", 0) - merged.get("rmse_a", 0)
    )

    cost_per_call = float(os.environ.get("LLM_COST_PER_CALL", "0.0005"))
    calls_per_player = float(os.environ.get("LLM_CALLS_PER_PLAYER", "10"))
    merged["llm_cost_estimate"] = cost_per_call * calls_per_player
    # naive ROI: improvement per unit cost (delta RMSE reduction per $)
    merged["roi_rmse_per_dollar"] = merged["delta_rmse"] / merged["llm_cost_estimate"]

    out_csv = out_csv or (Path(eval_a).parent / "llm_roi_report.csv")
    merged.to_csv(out_csv, index=False)
    print("Wrote LLM ROI report to", out_csv)


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--eval-a", required=True)
    p.add_argument("--eval-b", required=True)
    p.add_argument("--out", default=None)
    args = p.parse_args()
    main(args.eval_a, args.eval_b, args.out)
