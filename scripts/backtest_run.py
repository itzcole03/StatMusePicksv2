"""Run a deterministic smoke backtest and write a JSON report.

Usage:
  python scripts/backtest_run.py --output backend/models_store/backtest_reports/smoke_report.json

If no `--output` provided, writes to `backend/models_store/backtest_reports/smoke_report_<ts>.json`.
"""

import argparse
import datetime
import os
import pathlib
import sys
from datetime import timezone

import pandas as pd

# Ensure repo root is on sys.path so `backend` package imports work when invoked
repo_root = pathlib.Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from backend.evaluation.backtesting import BacktestEngine, write_report_json


def make_synthetic_df(n=200):
    # deterministic pseudo-random via numpy RNG seeded for CI reproducibility
    import numpy as np

    rng = np.random.RandomState(0)
    preds = rng.uniform(0.1, 0.9, size=n)
    actual = rng.binomial(1, preds)
    odds = [2.0 for _ in range(n)]
    return pd.DataFrame({"pred_prob": preds, "actual": actual, "odds": odds})


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", "-o", help="Output JSON report path", default=None)
    args = p.parse_args()

    df = make_synthetic_df(300)
    engine = BacktestEngine(start_bankroll=1000.0)
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
        "summary": res._asdict() if hasattr(res, "_asdict") else res.__dict__,
    }

    out = args.output
    if not out:
        ts = datetime.datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = os.path.join("backend", "models_store", "backtest_reports")
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, f"smoke_backtest_{ts}.json")

    write_report_json(report, out)
    print("Wrote backtest report to", out)


if __name__ == "__main__":
    main()
