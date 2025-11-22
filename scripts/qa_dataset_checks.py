"""QA checks for dataset time-split leakage and continuity.

Usage:
  python scripts/qa_dataset_checks.py --manifest backend/data/datasets/points_dataset_v20251119T043328Z_fcb745d9/dataset_manifest.json

Outputs a JSON report alongside the dataset manifest: dataset_qa_report.json
"""
import argparse
import json
from pathlib import Path
import pandas as pd
from collections import defaultdict


def load_manifest(path: Path):
    with open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def load_parts(manifest):
    parts = manifest.get('parts', {})
    dfs = {}
    for k in ['train','val','test']:
        p = parts.get(k)
        if not p:
            raise RuntimeError(f'missing part {k}')
        f = Path(p['files']['features'])
        df = pd.read_parquet(f)
        # ensure datetime
        if 'game_date' in df.columns:
            df['game_date'] = pd.to_datetime(df['game_date'])
        dfs[k]=df
    return dfs


def per_player_checks(dfs):
    players = set()
    for df in dfs.values():
        players.update(df['player'].unique())
    report = {'players_checked': len(players),'issues':[], 'per_player':{}}
    for p in sorted(players):
        pinfo = {'train_count':0,'val_count':0,'test_count':0,'train_max':None,'val_min':None,'val_max':None,'test_min':None,'overlap':False}
        if 'player' not in dfs['train'].columns:
            continue
        t = dfs['train'][dfs['train']['player']==p]
        v = dfs['val'][dfs['val']['player']==p]
        te = dfs['test'][dfs['test']['player']==p]
        if not t.empty:
            pinfo['train_count'] = int(len(t))
            pinfo['train_max'] = str(t['game_date'].max())
            pinfo['train_min'] = str(t['game_date'].min())
        if not v.empty:
            pinfo['val_count'] = int(len(v))
            pinfo['val_max'] = str(v['game_date'].max())
            pinfo['val_min'] = str(v['game_date'].min())
        if not te.empty:
            pinfo['test_count'] = int(len(te))
            pinfo['test_max'] = str(te['game_date'].max())
            pinfo['test_min'] = str(te['game_date'].min())
        # leakage checks: train.max < val.min and val.max < test.min when both present
        try:
            if pinfo.get('train_max') and pinfo.get('val_min'):
                if pd.to_datetime(pinfo['train_max']) >= pd.to_datetime(pinfo['val_min']):
                    pinfo['overlap']=True
            if pinfo.get('val_max') and pinfo.get('test_min'):
                if pd.to_datetime(pinfo['val_max']) >= pd.to_datetime(pinfo['test_min']):
                    pinfo['overlap']=True
        except Exception:
            pinfo['overlap']=True
        if pinfo['overlap']:
            report['issues'].append({'player':p,'detail':pinfo})
        report['per_player'][p]=pinfo
    return report


def global_checks(dfs):
    report = {}
    # check for duplicate (player, game_date) across splits
    combined = []
    for k,df in dfs.items():
        df2 = df[['player','game_date']].copy()
        df2['split']=k
        combined.append(df2)
    big = pd.concat(combined, ignore_index=True)
    big['game_date'] = pd.to_datetime(big['game_date'])
    dup = big.duplicated(subset=['player','game_date'], keep=False)
    dup_df = big[dup].sort_values(['player','game_date'])
    overlaps = []
    for player, g in dup_df.groupby('player'):
        overlaps.append({'player':player, 'rows': g.to_dict(orient='records')})
    report['duplicate_player_game_date_rows'] = len(dup_df)
    report['overlap_examples'] = overlaps[:20]
    # per-split date ranges
    ranges={}
    for k,df in dfs.items():
        if df.empty:
            ranges[k]=None
        else:
            ranges[k]={'min': str(df['game_date'].min()), 'max': str(df['game_date'].max()), 'rows': int(len(df))}
    report['ranges']=ranges
    return report


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--manifest', required=True)
    args = p.parse_args()
    mpath = Path(args.manifest)
    manifest = load_manifest(mpath)
    dfs = load_parts(manifest)
    per_player = per_player_checks(dfs)
    globalr = global_checks(dfs)
    out = {'manifest':str(mpath), 'per_player':per_player, 'global':globalr}
    # serialize timestamps to strings for JSON dump
    def _make_serializable(o):
        if isinstance(o, dict):
            return {k: _make_serializable(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_make_serializable(v) for v in o]
        try:
            # pandas Timestamp, datetime, numpy types
            import pandas as _pd
            import numpy as _np
            if isinstance(o, (_pd.Timestamp, _np.datetime64)):
                return str(o)
        except Exception:
            pass
        if hasattr(o, 'isoformat'):
            return str(o)
        return o

    out_path = mpath.parent / 'dataset_qa_report.json'
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(_make_serializable(out), fh, indent=2)
    print('Wrote QA report to', out_path)

if __name__=='__main__':
    main()
