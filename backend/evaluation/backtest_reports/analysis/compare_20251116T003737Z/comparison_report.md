# Calibration Comparison Report

Generated: 2025-11-16T00:37:37.258832+00:00

## Overview
Comparing an uncalibrated baseline run to a run with Platt-scaling calibration (fit on `train` split).

## Summary
| variant | run_dir | initial_bankroll | final_bankroll | roi | win_rate | total_bets | sharpe | max_drawdown | cagr |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | backend\evaluation\backtest_reports\analysis\backtest_20251116T003736Z | 1000.0 | 545.4843193824373 | -0.4545156806175627 | 0.0 | 30.0 | -31.419018428324296 | 0.4433833475689415 | -1.0 |
| calibrated | backend\evaluation\backtest_reports\analysis\backtest_20251116T003737Z | 1000.0 | 545.4843193824373 | -0.4545156806175627 | 0.0 | 30.0 | -31.419018428324296 | 0.4433833475689415 | -1.0 |

## Calibration Table (calibrated run)

| _bin | mean_pred | mean_obs | count |
| --- | --- | --- | --- |
| (-0.001, 0.1] | nan | nan | 0 |
| (0.1, 0.2] | nan | nan | 0 |
| (0.2, 0.3] | nan | nan | 0 |
| (0.3, 0.4] | nan | nan | 0 |
| (0.4, 0.5] | 0.4533914996761611 | 0.0 | 50 |
| (0.5, 0.6] | 0.5551796470082551 | 0.0 | 20 |
| (0.6, 0.7] | 0.6569646817818363 | 0.0 | 30 |
| (0.7, 0.8] | nan | nan | 0 |
| (0.8, 0.9] | nan | nan | 0 |
| (0.9, 1.0] | nan | nan | 0 |