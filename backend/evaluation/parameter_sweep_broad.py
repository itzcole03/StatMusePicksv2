"""Broader parameter sweep: runs two sweeps (Platt and K-fold Platt) over a small grid
and writes consolidated CSVs for each sweep.
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


def run_sweep(line_shifts: List[float], min_confidences: List[float], decimal_odds_list: List[float], max_fractions: List[float], method: str = 'platt', kfold_folds: int = 5):
    out_root = Path('backend/evaluation/backtest_reports/sweeps_broad')
    out_root.mkdir(parents=True, exist_ok=True)

    records = []

    for ls in line_shifts:
        for mc in min_confidences:
            for odds in decimal_odds_list:
                for mf in max_fractions:
                    print(f"Running sweep: ls={ls}, mc={mc}, odds={odds}, max_frac={mf}, method={method}")
                    argv = [
                        '--line-shift', str(ls),
                        '--decimal-odds', str(odds),
                        '--min-confidence', str(mc),
                        '--outdir', str(out_root),
                        '--max-fraction', str(mf),
                    ]
                    # choose calibration invocation based on method
                    if method == 'platt':
                        argv += ['--calibrate', '--calibration-split', 'train']
                    elif method == 'platt_kfold':
                        argv += ['--kfold-calibrate', '--kfold-folds', str(kfold_folds), '--calibration-split', 'train']
                    elif method == 'isotonic':
                        argv += ['--isotonic', '--calibration-split', 'train']
                    elif method == 'isotonic_kfold':
                        argv += ['--kfold-isotonic', '--kfold-folds', str(kfold_folds), '--calibration-split', 'train']
                    else:
                        # default to platt
                        argv += ['--calibrate', '--calibration-split', 'train']

                    runner.main(argv)

                    # pick the newest run dir under out_root
                    runs = sorted([p for p in out_root.iterdir() if p.is_dir()])
                    last = runs[-1]

                    meta = {}
                    if (last / 'metadata.json').exists():
                        with open(last / 'metadata.json', 'r') as fh:
                            meta = json.load(fh)

                    summary = {}
                    if (last / 'summary.csv').exists():
                        try:
                            sdf = pd.read_csv(last / 'summary.csv')
                            if not sdf.empty:
                                summary = sdf.iloc[0].to_dict()
                        except Exception:
                            pass

                    records.append({
                        'run_dir': str(last),
                        'line_shift': ls,
                        'decimal_odds': odds,
                        'min_confidence': mc,
                        'max_fraction': mf,
                        'kfold': kfold,
                        'predictions_rows': meta.get('predictions_rows'),
                        'actuals_rows': meta.get('actuals_rows'),
                        'initial_bankroll': summary.get('initial_bankroll'),
                        'final_bankroll': summary.get('final_bankroll'),
                        'roi': summary.get('roi'),
                        'brier_score': summary.get('brier_score'),
                        'win_rate': summary.get('win_rate'),
                        'total_bets': summary.get('total_bets'),
                    })

    out_csv = out_root / f'sweep_broad_{method}_{datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")}.csv'
    keys = ['run_dir','line_shift','decimal_odds','min_confidence','max_fraction','method','predictions_rows','actuals_rows','initial_bankroll','final_bankroll','roi','brier_score','win_rate','total_bets']
    with open(out_csv, 'w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        for r in records:
            writer.writerow({k: r.get(k) for k in keys})

    print('Sweep complete. Summary saved to:', out_csv)
    return out_csv


if __name__ == '__main__':
    # modest grid to keep runtime reasonable
    line_shifts = [0.5, 1.5]
    min_confidences = [0.15, 0.2, 0.25]
    decimal_odds_list = [1.9, 2.2]
    max_fractions = [0.01, 0.02]

    print('Running Platt-calibrated sweep')
    run_sweep(line_shifts, min_confidences, decimal_odds_list, max_fractions, method='platt')

    print('Running K-fold Platt-calibrated sweep')
    run_sweep(line_shifts, min_confidences, decimal_odds_list, max_fractions, method='platt_kfold', kfold_folds=5)

    print('Running Isotonic-calibrated sweep')
    run_sweep(line_shifts, min_confidences, decimal_odds_list, max_fractions, method='isotonic')

    print('Running K-fold Isotonic-calibrated sweep')
    run_sweep(line_shifts, min_confidences, decimal_odds_list, max_fractions, method='isotonic_kfold', kfold_folds=5)
