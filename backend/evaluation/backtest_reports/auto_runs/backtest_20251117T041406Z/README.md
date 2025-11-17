Backtest run: backtest_20251117T041406Z

Summary
-------
- Date (UTC): 2025-11-17T04:14:06Z
- Training CSV: `backend/data/training_datasets/points_dataset_combined_normalized.csv`
- Calibration: `isotonic_kfold_5`
- Command run:

  ```powershell
  $env:PYTHONPATH='C:\Users\bcmad\Downloads\StatMusePicksv2'
  & .\.venv\Scripts\python.exe backend/evaluation/run_backtest_with_metadata.py --training-csv backend/data/training_datasets/points_dataset_combined_normalized.csv --kfold-isotonic --kfold-folds 5 --min-confidence 0.6 --line-shift 1.5 --decimal-odds 2.2
  ```

Key outputs
-----------
- `bets.csv` — per-bet ledger (stakes, results, bankroll progression)
- `summary.csv` — summary metrics
- `metadata.json` — reproducibility metadata (calibration params, CLI args, python executable)
- `calibration.csv`, `calibration.png` — calibration table and reliability diagram
- `bankroll.png`, `cumulative_profit.png` — visualizations

Quick metrics (from `summary.csv`)
----------------------------------
- initial_bankroll: 1000.0
- final_bankroll: 1146.8647765793519
- roi: 0.14686477657935187
- win_rate: 0.5714285714285714
- total_bets: 28
- brier_score: 0.2724641891682776

Notes
-----
- Timestamps in some training rows mixed microsecond-only naive datetimes and timezone-aware strings; the runner normalizes both predictions and actuals to UTC to ensure deterministic parsing.
- This run is recorded on branch `feat/isotonic-ci-tests`; pushing these changes will update the existing PR.
