Backtest run: backtest_20251117T043922Z
=====================================

Summary
-------
- Run directory: `backend/evaluation/backtest_reports/auto_runs/backtest_20251117T043922Z`
- Timestamp (UTC): `2025-11-17T04:39:23.018021+00:00`
- Calibration: `isotonic_kfold` (5 folds)
- Betting args: `min_confidence=0.6`, `line_shift=1.5`, `decimal_odds=2.2`, `max_fraction_per_bet=0.02`

Top metrics
-----------
- Initial bankroll: `1000.0`
- Final bankroll: `1146.864776579352`
- ROI: `0.1468647765793518`
- Win rate: `0.5714285714285714`
- Total bets: `28`
- Sharpe: `1.3751913214567917`
- Max drawdown: `0.199268649250204`
- Brier score: `0.2724641891682776`

Artifacts produced (in this folder)
----------------------------------
- `bankroll.png` — bankroll over time
- `cumulative_profit.png` — cumulative profit plot
- `calibration.png` — reliability / calibration plot
- `bets.csv` — individual bets placed during simulation
- `summary.csv` — summary metrics (one-row)
- `calibration.csv` — numeric calibration table

Notes
-----
- Predictions/actuals rows: 158 each.
- The run coerces datetimes to timezone-aware UTC to avoid parsing issues.
- Some non-blocking pandas/sklearn warnings were observed (imputer warnings and groupby `observed` deprecation).

Suggested next steps
--------------------
- Upload these artifacts to the PR or CI artifacts bucket for review.
- If you want a consolidated comparison across runs, I can generate a `consolidated_summary.csv` that aggregates `summary.csv` across `auto_runs/`.

Command used
------------
```
python backend/evaluation/run_backtest_with_metadata.py \
  --training-csv backend/data/training_datasets/points_dataset_combined_normalized.csv \
  --kfold-isotonic --kfold-folds 5 \
  --min-confidence 0.6 --line-shift 1.5 --decimal-odds 2.2
```
