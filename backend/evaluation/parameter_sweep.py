"""Parameter sweep runner for backtests.

Runs `run_backtest_with_metadata.py` programmatically over a grid of parameters
and writes a consolidated `sweep_summary.csv` under `backtest_reports/sweeps/`.

Designed to follow roadmap best-practices: reproducible runs, per-run metadata,
and a single summary artifact for quick comparison.
"""
from __future__ import annotations

import csv
import datetime
import json
import os
from pathlib import Path
from typing import List

import pandas as pd

import backend.evaluation.run_backtest_with_metadata as runner


def run_grid(line_shifts: List[float], min_confidences: List[float], decimal_odds: float = 2.2, method: str = 'platt', kfold_folds: int = 5):
    out_root = Path('backend/evaluation/backtest_reports/sweeps')
    out_root.mkdir(parents=True, exist_ok=True)

    records = []

    for ls in line_shifts:
        for mc in min_confidences:
            print(f"Running sweep: line_shift={ls}, min_confidence={mc}")
            argv = [
                '--line-shift', str(ls),
                '--decimal-odds', str(decimal_odds),
                '--min-confidence', str(mc),
                '--outdir', str(out_root),
                '--calibration-split', 'train',
            ]
            if method == 'platt':
                argv += ['--calibrate']
            elif method == 'platt_kfold':
                argv += ['--kfold-calibrate', '--kfold-folds', str(kfold_folds)]
            elif method == 'isotonic':
                argv += ['--isotonic']
            elif method == 'isotonic_kfold':
                argv += ['--kfold-isotonic', '--kfold-folds', str(kfold_folds)]
            else:
                argv += ['--calibrate']
            # runner.main will create a timestamped run dir and print it
            runner.main(argv)

            # find the most recent run_dir in out_root
            runs = sorted([p for p in out_root.iterdir() if p.is_dir()])
            if not runs:
                print('No run directories found after runner')
                continue
            last = runs[-1]

            # read metadata and summary
            meta_path = last / 'metadata.json'
            summary_path = last / 'summary.csv'
            meta = {}
            if meta_path.exists():
                with open(meta_path, 'r') as fh:
                    meta = json.load(fh)

            summary = {}
            if summary_path.exists():
                try:
                    sdf = pd.read_csv(summary_path)
                    if not sdf.empty:
                        summary = sdf.iloc[0].to_dict()
                except Exception as e:
                    print('Failed reading summary.csv:', e)

            record = {
                'run_dir': str(last),
                'line_shift': ls,
                'decimal_odds': decimal_odds,
                'min_confidence': mc,
                'predictions_rows': meta.get('predictions_rows'),
                'actuals_rows': meta.get('actuals_rows'),
                'initial_bankroll': summary.get('initial_bankroll'),
                'final_bankroll': summary.get('final_bankroll'),
                'roi': summary.get('roi'),
                'brier_score': summary.get('brier_score'),
                'win_rate': summary.get('win_rate'),
                'total_bets': summary.get('total_bets'),
                'sharpe': summary.get('sharpe'),
                'max_drawdown': summary.get('max_drawdown'),
                'cagr': summary.get('cagr'),
                'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            records.append(record)

    # write consolidated CSV
    out_csv = out_root / 'sweep_summary.csv'
    keys = [
        'run_dir', 'line_shift', 'decimal_odds', 'min_confidence', 'predictions_rows', 'actuals_rows',
        'initial_bankroll', 'final_bankroll', 'roi', 'brier_score', 'win_rate', 'total_bets', 'sharpe', 'max_drawdown', 'cagr', 'timestamp'
    ]
    with open(out_csv, 'w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        for r in records:
            writer.writerow({k: r.get(k) for k in keys})

    print('Sweep complete. Summary saved to:', out_csv)
    return out_csv


if __name__ == '__main__':
    # small grid consistent with roadmap quick-scan
    line_shifts = [0.5, 1.0, 1.5, 2.0]
    min_confidences = [0.2, 0.3, 0.4, 0.5]
    print('Running Platt quick sweep')
    run_grid(line_shifts, min_confidences, decimal_odds=2.2, method='platt')

    print('Running Isotonic quick sweep')
    run_grid(line_shifts, min_confidences, decimal_odds=2.2, method='isotonic')
