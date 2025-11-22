"""Compute simple baseline: predict per-player training mean, evaluate MAE on val/test.

Usage:
  python scripts/baseline_eval.py --manifest <manifest.json>
"""
import argparse
from pathlib import Path
import pandas as pd
import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--manifest', required=True)
    args = p.parse_args()
    import json
    mpath = Path(args.manifest)
    manifest = json.load(open(mpath, 'r', encoding='utf-8'))
    parts = manifest.get('parts')
    def load_part(k):
        f = Path(parts[k]['files']['features'])
        df = pd.read_parquet(f)
        df['game_date'] = pd.to_datetime(df['game_date'])
        return df
    train = load_part('train')
    val = load_part('val')
    test = load_part('test')
    # per-player mean on train
    player_mean = train.groupby('player')['target'].mean()
    def eval_df(df, name):
        merged = df.join(player_mean, on='player', rsuffix='_pred')
        merged['pred'] = merged['target_pred']
        # fallback to global mean if player missing
        global_mean = train['target'].mean()
        merged['pred'] = merged['pred'].fillna(global_mean)
        mae = np.mean(np.abs(merged['target'] - merged['pred']))
        return mae
    val_mae = eval_df(val, 'val')
    test_mae = eval_df(test, 'test')
    print('Baseline per-player-mean MAE: val=', round(val_mae,3), ' test=', round(test_mae,3))

if __name__=='__main__':
    main()
