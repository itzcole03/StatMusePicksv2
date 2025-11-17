"""Run initial backtests for the 2023-2024 season (synthetic inputs).

This script generates a synthetic predictions + actuals CSV covering the
2023-10-15 -> 2024-04-15 window, runs three strategies, and writes reports
to `backend/evaluation/backtest_reports/`.

Strategies:
 - strategy_1_ev_positive: Bet when EV > 0
 - strategy_2_high_conf: Bet only when confidence >= 0.70 and EV > 0
 - strategy_3_underdogs: Bet only when decimal odds > 2.0 (underdogs)

This provides a deterministic, reproducible local run for Task 2.5.2.
"""
from __future__ import annotations

import os
import math
import datetime
from typing import Tuple

import numpy as np
import pandas as pd

from backend.evaluation.backtesting import BacktestEngine


def date_range(start: str, end: str):
    s = pd.to_datetime(start)
    e = pd.to_datetime(end)
    return pd.date_range(s, e, freq="D")


def build_synthetic_dataset(seed: int = 42) -> Tuple[pd.DataFrame, pd.DataFrame]:
    np.random.seed(seed)

    dates = date_range("2023-10-15", "2024-04-15")
    players = [f"Player {i}" for i in range(1, 61)]

    rows_actual = []
    rows_pred = []

    for d in dates:
        # simulate a subset of players playing each day
        n_play = np.random.poisson(6) + 3
        picked = np.random.choice(players, size=min(len(players), max(1, n_play)), replace=False)
        for p in picked:
            # actual performance (points) - player base + day noise
            base = 18 + (hash(p) % 6)  # small deterministic per-player offset
            actual = float(np.random.normal(loc=base, scale=6.0))
            actual = max(0.0, actual)
            rows_actual.append({"game_date": d.strftime("%Y-%m-%d"), "player": p, "actual_value": actual})

            # predicted: actual plus some prediction error (bias + noise)
            bias = 0.4  # slight optimistic bias in predictions
            pred_noise = float(np.random.normal(loc=bias, scale=4.0))
            predicted = max(0.0, actual + pred_noise)

            # market line: simulated as actual + market_noise (market often close to true)
            market_noise = float(np.random.normal(loc=0.0, scale=2.5))
            line = max(0.0, actual + market_noise)

            # decimal odds: odds >1; make favorites <2, underdogs >2
            # create variability based on (line - predicted)
            odds = 2.0 + (line - predicted) / 8.0
            odds = max(1.5, min(odds, 5.0))

            # probability estimate (sigmoid of difference scaled)
            diff = predicted - line
            p_over = 1.0 / (1.0 + math.exp(-diff / 3.0))

            # confidence: map absolute diff to [0.5, 0.95]
            conf = 0.5 + (min(abs(diff), 6.0) / 6.0) * 0.45

            # expected value per-unit stake (b*p - (1-p)) where b = odds-1
            b = odds - 1.0
            ev = b * p_over - (1.0 - p_over)

            rows_pred.append(
                {
                    "game_date": d.strftime("%Y-%m-%d"),
                    "player": p,
                    "line": line,
                    "predicted_value": predicted,
                    "over_probability": p_over,
                    "confidence": conf,
                    "expected_value": ev,
                    "decimal_odds": odds,
                }
            )

    actuals = pd.DataFrame(rows_actual)
    preds = pd.DataFrame(rows_pred)

    # sort for readability
    actuals = actuals.sort_values(["game_date", "player"]).reset_index(drop=True)
    preds = preds.sort_values(["game_date", "player"]).reset_index(drop=True)

    return preds, actuals


def run_strategies(preds: pd.DataFrame, actuals: pd.DataFrame, outdir: str):
    os.makedirs(outdir, exist_ok=True)

    # Strategy 1: Bet when EV > 0
    engine1 = BacktestEngine(preds)
    res1 = engine1.run(actuals, initial_bankroll=1000.0, min_confidence=0.0, require_ev_positive=True)
    dir1 = BacktestEngine.save_report(res1, outdir, run_name="strategy_1_ev_positive_2023_24")

    # Strategy 2: Bet only high-confidence (>= 0.70) AND EV > 0
    engine2 = BacktestEngine(preds)
    res2 = engine2.run(actuals, initial_bankroll=1000.0, min_confidence=0.70, require_ev_positive=True)
    dir2 = BacktestEngine.save_report(res2, outdir, run_name="strategy_2_high_conf_2023_24")

    # Strategy 3: Bet only underdogs (decimal_odds > 2.0)
    underdog_preds = preds[preds["decimal_odds"] > 2.0].copy()
    engine3 = BacktestEngine(underdog_preds)
    res3 = engine3.run(actuals, initial_bankroll=1000.0, min_confidence=0.0, require_ev_positive=True)
    dir3 = BacktestEngine.save_report(res3, outdir, run_name="strategy_3_underdogs_2023_24")

    summary = pd.DataFrame(
        [
            {
                "strategy": "ev_positive",
                "roi": res1.roi,
                "final_bankroll": res1.final_bankroll,
                "total_bets": res1.total_bets,
                "win_rate": res1.win_rate,
            },
            {
                "strategy": "high_conf",
                "roi": res2.roi,
                "final_bankroll": res2.final_bankroll,
                "total_bets": res2.total_bets,
                "win_rate": res2.win_rate,
            },
            {
                "strategy": "underdogs",
                "roi": res3.roi,
                "final_bankroll": res3.final_bankroll,
                "total_bets": res3.total_bets,
                "win_rate": res3.win_rate,
            },
        ]
    )

    summary.to_csv(os.path.join(outdir, "summary_2023_24.csv"), index=False)

    print("Backtests complete. Reports saved to:")
    print(dir1)
    print(dir2)
    print(dir3)
    print("Summary:")
    print(summary)


def main():
    outdir = "backend/evaluation/backtest_reports"
    preds, actuals = build_synthetic_dataset(seed=20251115)

    # write inputs for traceability
    inp_dir = os.path.join(outdir, "inputs_2023_24")
    os.makedirs(inp_dir, exist_ok=True)
    preds.to_csv(os.path.join(inp_dir, "predictions_2023_24.csv"), index=False)
    actuals.to_csv(os.path.join(inp_dir, "actuals_2023_24.csv"), index=False)

    run_strategies(preds, actuals, outdir)


if __name__ == "__main__":
    main()
