"""Convert training dataset rows into predictions and actuals CSVs for backtesting.

Creates two CSVs under `backend/evaluation/backtest_reports/inputs_from_training/`:
 - predictions_from_training.csv
 - actuals_from_training.csv

This script is deterministic and self-contained (no extra deps beyond pandas/numpy).
"""
from __future__ import annotations

import argparse
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
import json
from typing import Optional

from backend.evaluation import calibration as _calib


def normal_cdf(z: float) -> float:
    """Simple normal CDF using math.erf to avoid an extra scipy dependency."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def build_predictions(df: pd.DataFrame, require_test_split: bool = True) -> pd.DataFrame:
    # Work with a copy and ensure lowercase columns
    df = df.rename(columns={c: c.lower() for c in df.columns}).copy()
    # If there is a 'split' column and caller requests it, prefer the test split
    if require_test_split and 'split' in df.columns and df['split'].nunique() > 0:
        df = df[df['split'] == 'test']

    if df.empty:
        raise RuntimeError('No rows selected for predictions (no test split rows)')

    # Choose fields for predicted value and market line
    # predicted_value: exponential_moving_avg or last_5_avg
    if 'exponential_moving_avg' in df.columns:
        pred_base = df['exponential_moving_avg'].astype(float)
    elif 'last_5_avg' in df.columns:
        pred_base = df['last_5_avg'].astype(float)
    else:
        pred_base = df['season_avg'].astype(float)

    # Use season_avg as a proxy for the 'market line' (where available). Shift slightly
    # to create a small edge so the backtester can place bets in some cases.
    if 'season_avg' in df.columns:
        market_line = df['season_avg'].astype(float) - 0.5
    else:
        market_line = pred_base - 0.5

    # Estimate uncertainty per-row (std); fall back to a reasonable default
    sigma = None
    for cname in ('last_10_std', 'last_5_std', 'last_3_std', 'recent_std'):
        if cname in df.columns:
            sigma = df[cname].astype(float)
            break
    if sigma is None:
        sigma = pd.Series(np.full(len(df), 3.0))

    # Build probabilities using a normal model: P(actual > line) = 1 - CDF((line - mu)/sigma)
    mu = pred_base
    sigma = sigma.fillna(3.0).replace(0.0, 3.0)
    z = (market_line - mu) / (sigma + 1e-6)
    over_p = 1.0 - z.apply(normal_cdf)

    # Confidence heuristic: inverse of short-term volatility mapped to 20..95
    if 'last_3_std' in df.columns:
        vol = df['last_3_std'].astype(float).fillna(3.0)
    else:
        vol = sigma
    maxv = max(float(vol.max()), 1.0)
    conf = (1.0 / (1.0 + vol)) * (maxv / (maxv + 1.0))
    conf = np.clip(conf, 0.2, 0.95)
    # Backtester normalizes >1 values by dividing by 100 when >1, so keep in 0-1.

    # Decimal odds - use 2.0 as default market odds
    decimal_odds = 2.0
    b = decimal_odds - 1.0
    p = over_p
    ev_per_unit = b * p - (1.0 - p)

    out = pd.DataFrame({
        'game_date': df['game_date'],
        'player': df['player'],
        'line': market_line,
        'predicted_value': mu,
        'over_probability': p,
        'confidence': conf,
        'expected_value': ev_per_unit,
        'decimal_odds': decimal_odds,
    })

    return out


def build_actuals(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={c: c.lower() for c in df.columns}).copy()
    if 'target' in df.columns:
        df['actual_value'] = pd.to_numeric(df['target'], errors='coerce')
    elif 'actual_value' in df.columns:
        df['actual_value'] = pd.to_numeric(df['actual_value'], errors='coerce')
    else:
        raise RuntimeError('Training dataset lacks a target/actual column')

    out = pd.DataFrame({
        'game_date': df['game_date'],
        'player': df['player'],
        'actual_value': df['actual_value'],
    })
    return out


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--training-csv', default='backend/data/training_datasets/points_dataset_174f1d9ac88b.csv')
    p.add_argument('--outdir', default='backend/evaluation/backtest_reports/inputs_from_training')
    p.add_argument('--line-shift', type=float, default=0.5, help='Subtract this value from season_avg to form market line (larger -> more underpriced markets)')
    p.add_argument('--decimal-odds', type=float, default=2.0, help='Market decimal odds to assume for all rows')
    p.add_argument('--split', type=str, default='test', help="Which split to select from the training CSV ('test','val','train' or 'all')")
    p.add_argument('--calibrate', action='store_true', help='Fit Platt-scaling calibration using a specified calibration split (see --calibration-split)')
    p.add_argument('--calibration-split', type=str, default='train', help="Which split to use for fitting calibration parameters ('train','val','all')")
    args = p.parse_args(argv)

    src = Path(args.training_csv)
    if not src.exists():
        raise SystemExit(f'Training CSV not found: {src}')

    os.makedirs(args.outdir, exist_ok=True)

    df = pd.read_csv(src)
    full_df = df.copy()

    # select split if requested (for predictions/actuals output)
    sel = args.split.lower()
    if sel != 'all' and 'split' in full_df.columns:
        df = full_df[full_df['split'].astype(str).str.lower() == sel]
    else:
        df = full_df.copy()

    if df.empty:
        raise SystemExit('No rows selected from training CSV after applying split filter')

    # build predictions and actuals with provided parameters
    preds = build_predictions(df)
    actuals = build_actuals(df)

    # apply line shift and decimal odds overrides
    preds['line'] = preds['line'].astype(float) - float(args.line_shift)
    preds['decimal_odds'] = float(args.decimal_odds)

    preds_path = os.path.join(args.outdir, 'predictions_from_training.csv')
    actuals_path = os.path.join(args.outdir, 'actuals_from_training.csv')

    # Optional calibration: fit Platt scaling on a calibration split (selected from the full training CSV)
    if args.calibrate:
        calib_split = args.calibration_split.lower()
        if calib_split != 'all' and 'split' in full_df.columns:
            calib_df = full_df[full_df['split'].astype(str).str.lower() == calib_split]
        else:
            calib_df = full_df.copy()

        if not calib_df.empty:
            # Build predictions+actuals for calibration set
            p_preds = build_predictions(calib_df, require_test_split=False)
            p_actuals = build_actuals(calib_df)
            merged = pd.merge(p_preds, p_actuals, on=['game_date', 'player'], how='inner')

            # derive binary outcome using line or predicted_value similar to backtesting
            def _true_outcome(row):
                if not pd.isna(row.get('line')):
                    return 1.0 if float(row.get('actual_value')) > float(row.get('line')) else 0.0
                else:
                    pv = row.get('predicted_value')
                    check = float(pv) if (pv is not None and not pd.isna(pv)) else 0.0
                    return 1.0 if float(row.get('actual_value')) > check else 0.0

            merged['_true'] = merged.apply(_true_outcome, axis=1)
            p_arr = merged['over_probability'].fillna(0.0).astype(float).to_numpy()
            y_arr = merged['_true'].astype(float).to_numpy()
            if len(p_arr) >= 10:
                a, b = _calib.fit_platt_scaling(p_arr, y_arr)
                preds['over_probability'] = _calib.apply_platt(preds['over_probability'].astype(float).to_numpy(), a, b)
                # save calibration params for reproducibility
                try:
                    with open(os.path.join(args.outdir, 'calibration_params.json'), 'w') as fh:
                        json.dump({'method': 'platt', 'a': a, 'b': b, 'calibration_split': args.calibration_split}, fh, indent=2)
                except Exception:
                    pass

    preds.to_csv(preds_path, index=False)
    actuals.to_csv(actuals_path, index=False)

    print('Wrote:')
    print('  ', preds_path)
    print('  ', actuals_path)


if __name__ == '__main__':
    main()
