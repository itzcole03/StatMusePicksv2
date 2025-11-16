r"""Run an uncalibrated and calibrated backtest and produce a short comparison report.

Produces:
 - CSV: consolidated_summary.csv
 - Markdown: comparison_report.md

Usage (from repo root):
  $env:PYTHONPATH='C:\Users\bcmad\Downloads\StatMusePicksv2'; & .\.venv\Scripts\python.exe backend/evaluation/analysis/compare_calibration.py

The script runs two backtests using `run_backtest_with_metadata` programmatically:
 - uncalibrated (baseline)
 - calibrated (Platt scaling fit on 'train' split)

It writes outputs under `backend/evaluation/backtest_reports/analysis/compare_<timestamp>/`.
"""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import pandas as pd
import sys

from backend.evaluation import run_backtest_with_metadata as runner


def run_and_collect(line_shift=1.5, decimal_odds=2.2, min_confidence=0.2, method: str | None = None):
    argv = [
        '--line-shift', str(line_shift),
        '--decimal-odds', str(decimal_odds),
        '--min-confidence', str(min_confidence),
        '--outdir', 'backend/evaluation/backtest_reports/analysis',
    ]
    if method is not None:
        # map method strings to runner flags
        if method == 'platt':
            argv += ['--calibrate', '--calibration-split', 'train']
        elif method == 'platt_kfold':
            argv += ['--kfold-calibrate', '--kfold-folds', '5', '--calibration-split', 'train']
        elif method == 'isotonic':
            argv += ['--isotonic', '--calibration-split', 'train']
        elif method == 'isotonic_kfold':
            argv += ['--kfold-isotonic', '--kfold-folds', '5', '--calibration-split', 'train']

    # runner.main writes run_dir and metadata. Capture directory set before/after
    out_root = Path('backend/evaluation/backtest_reports/analysis')
    before = set(p for p in out_root.iterdir() if p.is_dir()) if out_root.exists() else set()
    runner.main(argv)
    after = set(p for p in out_root.iterdir() if p.is_dir())
    new = sorted(list(after - before))
    if new:
        last = new[-1]
    else:
        # fallback: most recent
        runs = sorted([p for p in out_root.iterdir() if p.is_dir()])
        if not runs:
            raise SystemExit('No run directories found')
        last = runs[-1]

    meta = {}
    meta_path = last / 'metadata.json'
    if meta_path.exists():
        with open(meta_path, 'r') as fh:
            meta = json.load(fh)

    summary = {}
    summary_path = last / 'summary.csv'
    if summary_path.exists():
        try:
            sdf = pd.read_csv(summary_path)
            if not sdf.empty:
                summary = sdf.iloc[0].to_dict()
        except Exception:
            summary = {}

    calib_df = None
    calib_path = last / 'calibration.csv'
    if calib_path.exists():
        try:
            calib_df = pd.read_csv(calib_path)
        except Exception:
            calib_df = None

    return {
        'run_dir': str(last),
        'metadata': meta,
        'summary': summary,
        'calibration': calib_df,
    }


def produce_report(results: list[dict], outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    # Consolidated CSV
    for res in results:
        try:
            if isinstance(res, dict):
                meta = res.get('metadata') or {}
            else:
                meta = {}
            if isinstance(meta, dict):
                variant = meta.get('calibration_params', {}).get('method') or 'baseline'
            else:
                variant = 'baseline'
        except Exception:
            variant = 'baseline'
        rec = {'variant': variant, 'run_dir': res.get('run_dir')}
        summary = res.get('summary') or {}
        rec.update({k: summary.get(k) for k in ('initial_bankroll', 'final_bankroll', 'roi', 'win_rate', 'total_bets', 'sharpe', 'max_drawdown', 'cagr')})
        rows.append(rec)

    df = pd.DataFrame(rows)
    csv_path = outdir / 'consolidated_summary.csv'
    df.to_csv(csv_path, index=False)

    # Markdown report
    md = []
    md.append('# Calibration Comparison Report')
    md.append('')
    md.append(f'Generated: {datetime.datetime.now(datetime.timezone.utc).isoformat()}')
    md.append('')
    md.append('## Overview')
    md.append('Comparing baseline and multiple calibrated variants (Platt and Isotonic, with optional k-fold variants) fit on `train` split.')
    md.append('')
    md.append('## Summary')
    # Render summary table manually to avoid optional tabulate dependency
    cols = list(df.columns)
    header = '| ' + ' | '.join(cols) + ' |'
    sep = '| ' + ' | '.join(['---'] * len(cols)) + ' |'
    md.append(header)
    md.append(sep)
    for _, r in df.iterrows():
        row = '| ' + ' | '.join([str(r.get(c, '')) for c in cols]) + ' |'
        md.append(row)
    md.append('')

    # include calibration tables for each calibrated variant if present
    for res in results:
        try:
            if isinstance(res, dict):
                meta = res.get('metadata') or {}
            else:
                meta = {}
            method = meta.get('calibration_params', {}).get('method') if isinstance(meta, dict) else None
        except Exception:
            method = None
        if not method:
            continue
        md.append(f'## Calibration: {method}')
        md.append('')
        calib_df = res.get('calibration')
        if calib_df is not None:
            try:
                ccols = list(calib_df.columns)
                md.append('| ' + ' | '.join(ccols) + ' |')
                md.append('| ' + ' | '.join(['---'] * len(ccols)) + ' |')
                for _, r in calib_df.iterrows():
                    md.append('| ' + ' | '.join([str(r.get(c, '')) for c in ccols]) + ' |')
            except Exception:
                md.append('Could not render calibration table.')
        else:
            md.append('No calibration table produced for this run.')
        md.append('')

    md_path = outdir / 'comparison_report.md'
    md_text = '\n'.join(md)
    with open(md_path, 'w', encoding='utf-8') as fh:
        fh.write(md_text)

    return csv_path, md_path


def main():
    # chosen representative params
    ls = 1.5
    odds = 2.2
    mc = 0.2


    print('Running baseline (uncalibrated)')
    baseline = run_and_collect(line_shift=ls, decimal_odds=odds, min_confidence=mc, method=None)

    results = [baseline]

    # run multiple calibration variants
    for method in ('platt', 'platt_kfold', 'isotonic', 'isotonic_kfold'):
        print(f'Running calibrated variant: {method}')
        res = run_and_collect(line_shift=ls, decimal_odds=odds, min_confidence=mc, method=method)
        results.append(res)

    ts = datetime.datetime.now(datetime.timezone.utc).strftime('compare_%Y%m%dT%H%M%SZ')
    outdir = Path('backend/evaluation/backtest_reports/analysis') / ts
    csv_path, md_path = produce_report(results, outdir)

    print('Report written:')
    print(' ', csv_path)
    print(' ', md_path)


if __name__ == '__main__':
    main()
