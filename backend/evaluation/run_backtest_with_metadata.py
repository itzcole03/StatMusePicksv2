"""Run conversion + backtest and save a metadata JSON for reproducibility.

Usage (from repo root with PYTHONPATH set):
  python backend/evaluation/run_backtest_with_metadata.py --line-shift 1.5 --decimal-odds 2.2 --min-confidence 0.25

This script imports the converter and BacktestEngine to run everything in-process
and writes a `metadata.json` into the output run directory alongside the reports.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import sys

import pandas as pd

from backend.evaluation.convert_training_to_predictions import build_predictions, build_actuals
from backend.evaluation.backtesting import BacktestEngine


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--training-csv', default='backend/data/training_datasets/points_dataset_174f1d9ac88b.csv')
    p.add_argument('--outdir', default='backend/evaluation/backtest_reports/auto_runs')
    p.add_argument('--line-shift', type=float, default=0.5)
    p.add_argument('--decimal-odds', type=float, default=2.0)
    p.add_argument('--split', type=str, default='test')
    p.add_argument('--calibrate', action='store_true', help='Fit Platt-scaling calibration using a specified calibration split before backtesting')
    p.add_argument('--calibration-split', type=str, default='train', help="Split to use for calibration fitting ('train','val','all')")
    p.add_argument('--kfold-calibrate', action='store_true', help='Fit K-fold Platt-scaling calibration before backtesting')
    p.add_argument('--kfold-folds', type=int, default=5, help='Number of folds for K-fold calibration')
    p.add_argument('--isotonic', action='store_true', help='Fit isotonic (PAV) calibration using a specified calibration split before backtesting')
    p.add_argument('--kfold-isotonic', action='store_true', help='Fit K-fold isotonic calibration before backtesting')
    p.add_argument('--max-fraction', type=float, default=0.02, help='Cap fraction of bankroll per bet')
    p.add_argument('--min-confidence', type=float, default=0.6)
    p.add_argument('--initial-bankroll', type=float, default=1000.0)
    args = p.parse_args(argv)

    src = Path(args.training_csv)
    if not src.exists():
        print(f"Training CSV not found: {src}")
        raise SystemExit(1)

    os.makedirs(args.outdir, exist_ok=True)

    df_full = pd.read_csv(src)
    df = df_full.copy()
    if args.split.lower() != 'all' and 'split' in df_full.columns:
        df = df_full[df_full['split'].astype(str).str.lower() == args.split.lower()]

    preds = build_predictions(df)
    actuals = build_actuals(df)

    preds['line'] = preds['line'].astype(float) - float(args.line_shift)
    preds['decimal_odds'] = float(args.decimal_odds)

    # Optional calibration: fit on a calibration split from the same training CSV
    calib_params = None
    if args.calibrate:
        calib_split = args.calibration_split.lower()
        if calib_split != 'all' and 'split' in df_full.columns:
            calib_df = df_full[df_full['split'].astype(str).str.lower() == calib_split]
        else:
            calib_df = df_full.copy()

        if not calib_df.empty:
            p_preds = build_predictions(calib_df, require_test_split=False)
            p_actuals = build_actuals(calib_df)
            merged = pd.merge(p_preds, p_actuals, on=['game_date', 'player'], how='inner')

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
                from backend.evaluation import calibration as _calib
                # Prefer Platt by default (backwards compatible)
                if args.kfold_calibrate:
                    a, b = _calib.fit_platt_kfold(p_arr, y_arr, k=args.kfold_folds)
                    method = f'platt_kfold_{args.kfold_folds}'
                    preds['over_probability'] = _calib.apply_platt(preds['over_probability'].astype(float).to_numpy(), a, b)
                    calib_params = {'method': method, 'a': a, 'b': b, 'calibration_split': args.calibration_split}
                else:
                    a, b = _calib.fit_platt_scaling(p_arr, y_arr)
                    method = 'platt'
                    preds['over_probability'] = _calib.apply_platt(preds['over_probability'].astype(float).to_numpy(), a, b)
                    calib_params = {'method': method, 'a': a, 'b': b, 'calibration_split': args.calibration_split}

    # Isotonic calibration options
    if args.isotonic or args.kfold_isotonic:
        # reuse calibration split selection above
        calib_split = args.calibration_split.lower()
        if calib_split != 'all' and 'split' in df_full.columns:
            calib_df = df_full[df_full['split'].astype(str).str.lower() == calib_split]
        else:
            calib_df = df_full.copy()

        if not calib_df.empty:
            p_preds = build_predictions(calib_df, require_test_split=False)
            p_actuals = build_actuals(calib_df)
            merged = pd.merge(p_preds, p_actuals, on=['game_date', 'player'], how='inner')
            merged['_true'] = merged.apply(lambda row: 1.0 if float(row.get('actual_value')) > float(row.get('line') if not pd.isna(row.get('line')) else row.get('predicted_value')) else 0.0, axis=1)
            p_arr = merged['over_probability'].fillna(0.0).astype(float).to_numpy()
            y_arr = merged['_true'].astype(float).to_numpy()
            if len(p_arr) >= 10:
                from backend.evaluation import calibration as _calib
                if args.kfold_isotonic:
                    models = _calib.fit_isotonic_kfold(p_arr, y_arr, k=args.kfold_folds)
                    # apply ensemble average of k models
                    preds['over_probability'] = _calib.apply_isotonic_ensemble(preds['over_probability'].astype(float).to_numpy(), models)
                    # serialize models (xs, ys lists)
                    serialized = [{'xs': xs.tolist(), 'ys': ys.tolist()} for xs, ys in models]
                    calib_params = {'method': f'isotonic_kfold_{args.kfold_folds}', 'models': serialized, 'calibration_split': args.calibration_split}
                else:
                    xs, ys = _calib.fit_isotonic(p_arr, y_arr)
                    preds['over_probability'] = _calib.apply_isotonic(preds['over_probability'].astype(float).to_numpy(), xs, ys)
                    calib_params = {'method': 'isotonic', 'xs': xs.tolist(), 'ys': ys.tolist(), 'calibration_split': args.calibration_split}

    engine = BacktestEngine(preds)
    result = engine.run(
        actuals,
        initial_bankroll=args.initial_bankroll,
        min_confidence=args.min_confidence,
        max_fraction_per_bet=args.max_fraction,
    )

    # Save report and metadata
    run_name = datetime.datetime.now(datetime.timezone.utc).strftime("backtest_%Y%m%dT%H%M%SZ")
    run_dir = engine.save_report(result, args.outdir, run_name=run_name)

    metadata = {
        'training_csv': str(src),
        'line_shift': args.line_shift,
        'decimal_odds': args.decimal_odds,
        'split': args.split,
        'calibrated': bool(calib_params is not None),
        'calibration_params': calib_params,
        'max_fraction_per_bet': args.max_fraction,
        'min_confidence': args.min_confidence,
        'initial_bankroll': args.initial_bankroll,
        'predictions_rows': len(preds),
        'actuals_rows': len(actuals),
        'run_dir': run_dir,
        'timestamp_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'python_executable': sys.executable,
    }

    with open(os.path.join(run_dir, 'metadata.json'), 'w') as fh:
        json.dump(metadata, fh, indent=2)

    print('Run complete. Reports and metadata saved to:')
    print('  ', run_dir)


if __name__ == '__main__':
    main()
