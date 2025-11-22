"""Run a simple backtest using cached team game logs (2023-24).

This script constructs predicted probabilities from a rolling average
of team points, uses the season average as a proxy market line, and
runs the `BacktestEngine` to simulate betting results.
"""
import json
import os
from pathlib import Path
import datetime
import pandas as pd
import numpy as np

repo_root = Path(__file__).resolve().parents[1]
data_dir = repo_root / 'backend' / 'data' / 'cached_game_logs'
out_dir = repo_root / 'backend' / 'models_store' / 'backtest_reports'
os.makedirs(out_dir, exist_ok=True)

from backend.evaluation.backtesting import BacktestEngine, write_report_json


def process_team_file(path: Path) -> pd.DataFrame:
    with open(path, 'r', encoding='utf-8') as fh:
        arr = json.load(fh)
    # Expect each item to have GAME_DATE and PTS
    df = pd.DataFrame(arr)
    if df.empty:
        return df
    # normalize and sort by date ascending
    try:
        df['GAME_DATE'] = pd.to_datetime(df['GAME_DATE'], errors='coerce')
    except Exception:
        pass
    df = df.sort_values('GAME_DATE').reset_index(drop=True)

    # compute season average as market line
    df['season_avg'] = df['PTS'].expanding().mean().shift(1).fillna(method='bfill')
    # rolling prediction: mean of last 3 games (previous games)
    df['predicted_value'] = df['PTS'].rolling(window=3, min_periods=1).mean().shift(1).fillna(method='bfill')

    # compute predicted probability via sigmoid centered on season_avg
    df['pred_prob'] = 1.0 / (1.0 + np.exp(-(df['predicted_value'] - df['season_avg'])))
    # actual outcome: 1 if PTS > season_avg
    df['actual'] = (df['PTS'] > df['season_avg']).astype(int)
    # market odds placeholder (decimal)
    df['odds'] = 1.909
    # keep columns
    return df[['GAME_DATE', 'PTS', 'predicted_value', 'season_avg', 'pred_prob', 'actual', 'odds']]


def main():
    all_files = sorted([p for p in data_dir.glob('*.json') if '2023-24' in p.name or '2024' in p.name])
    if not all_files:
        print('No cached game logs found under', data_dir)
        return

    combined = []
    for p in all_files:
        df = process_team_file(p)
        if df is None or df.empty:
            continue
        # tag team file
        team = p.stem
        df['team_file'] = team
        combined.append(df)

    if not combined:
        print('No usable game data parsed.')
        return

    df_all = pd.concat(combined, ignore_index=True)
    # run backtest engine using DataFrame interface
    engine = BacktestEngine(start_bankroll=1000.0)
    res = engine.run(df_all, prob_col='pred_prob', actual_col='actual', odds_col='odds', stake_mode='flat', flat_stake=5.0)

    report = {
        'generated_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
        'summary': res._asdict() if hasattr(res, '_asdict') else res.__dict__,
        'n_records': len(df_all),
    }

    out_path = out_dir / f'real_season_backtest_{datetime.datetime.now().strftime("%Y%m%dT%H%M%S")}.json'
    write_report_json(report, str(out_path))
    print('Wrote backtest report to', out_path)


if __name__ == '__main__':
    main()
