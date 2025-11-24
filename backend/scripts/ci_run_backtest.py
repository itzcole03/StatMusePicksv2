#!/usr/bin/env python3
"""CI helper: run a small backtest and write CSV/JSON reports into `--output-dir`.

This is intended for CI to validate backtesting logic and produce a downloadable report.
"""
import argparse
import json
import os
import datetime
import pandas as pd

from backend.evaluation.backtesting import BacktestEngine


def make_sample_df():
    # Build sample dataset with mixed outcomes and probabilities
    data = []
    actuals = [1,0,1,1,0,1,0,1,1,0]
    probs = [0.6,0.45,0.55,0.7,0.4,0.65,0.35,0.6,0.58,0.3]
    odds = [2.0] * len(actuals)
    for p,a,o in zip(probs, actuals, odds):
        data.append({"pred_prob": p, "odds": o, "actual": a})
    return pd.DataFrame(data)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output-dir', default='artifacts')
    args = p.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    df = make_sample_df()

    engine = BacktestEngine(start_bankroll=1000.0)
    res_flat = engine.run(df, stake_mode='flat', flat_stake=50.0)
    res_kelly = engine.run(df, stake_mode='kelly', kelly_cap=0.1)

    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out_base = os.path.join(args.output_dir, f'backtest_report_{ts}')
    json_path = out_base + '.json'
    csv_path = out_base + '.csv'

    # Prepare report dict
    report = {
        'run_at': ts,
        'flat': res_flat.__dict__,
        'kelly': res_kelly.__dict__,
    }

    # Write JSON
    with open(json_path, 'w') as f:
        json.dump(report, f, indent=2)

    # Write CSV summary
    summary = pd.DataFrame([
        {**{'mode': 'flat'}, **res_flat.__dict__},
        {**{'mode': 'kelly'}, **res_kelly.__dict__},
    ])
    summary.to_csv(csv_path, index=False)

    print('Wrote backtest reports:', json_path, csv_path)


if __name__ == '__main__':
    main()
