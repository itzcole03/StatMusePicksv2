# Calibration Comparison Report

Generated: 2025-11-16T06:19:15.322987+00:00

## Overview
Comparing baseline and multiple calibrated variants (Platt and Isotonic, with optional k-fold variants) fit on `train` split.

## Summary
| variant | run_dir | initial_bankroll | final_bankroll | roi | win_rate | total_bets | sharpe | max_drawdown | cagr |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | backend\evaluation\backtest_reports\analysis\backtest_20251116T061913Z | 1000.0 | 545.4843193824373 | -0.4545156806175627 | 0.0 | 30.0 | -31.419018428324296 | 0.4433833475689415 | -1.0 |
| platt | backend\evaluation\backtest_reports\analysis\backtest_20251116T061914Z | 1000.0 | 545.4843193824373 | -0.4545156806175627 | 0.0 | 30.0 | -31.419018428324296 | 0.4433833475689415 | -1.0 |
| baseline | backend\evaluation\backtest_reports\analysis\compare_20251116T061816Z | nan | nan | nan | nan | nan | nan | nan | nan |
| baseline | backend\evaluation\backtest_reports\analysis\compare_20251116T061816Z | nan | nan | nan | nan | nan | nan | nan | nan |
| isotonic_kfold_5 | backend\evaluation\backtest_reports\analysis\backtest_20251116T061915Z | 1000.0 | 545.4843193824373 | -0.4545156806175627 | 0.0 | 30.0 | -31.419018428324296 | 0.4433833475689415 | -1.0 |

## Calibration: platt

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

## Calibration: isotonic_kfold_5

| _bin | mean_pred | mean_obs | count |
| --- | --- | --- | --- |
| (-0.001, 0.1] | nan | nan | 0 |
| (0.1, 0.2] | nan | nan | 0 |
| (0.2, 0.3] | 0.2221115371627067 | 0.0 | 40 |
| (0.3, 0.4] | 0.3623654530557707 | 0.0 | 20 |
| (0.4, 0.5] | 0.4584493180660226 | 0.0 | 20 |
| (0.5, 0.6] | nan | nan | 0 |
| (0.6, 0.7] | 0.6561879784373076 | 0.0 | 10 |
| (0.7, 0.8] | 0.7862751044161707 | 0.0 | 10 |
| (0.8, 0.9] | nan | nan | 0 |
| (0.9, 1.0] | nan | nan | 0 |
