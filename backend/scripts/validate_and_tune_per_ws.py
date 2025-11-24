"""Validate and (optionally) tune PER/WS prototype estimates.

Usage:
  python backend/scripts/validate_and_tune_per_ws.py [--canonical-csv PATH] [--use-defaults]

If `--canonical-csv` is provided it should contain columns: `player,season,PER,WS`.
If `--use-defaults` is passed the script will use a small built-in canonical mapping
for the sample players so the tuning run can execute offline.

The script reads the latest `backend/models_store/per_ws_playbyplay_sample_*.json`
file produced by `compute_per_ws_sample.py`, computes scale factors to map prototype
estimates onto canonical values (least-squares single multiplier per metric), and
writes a report to `backend/models_store/compare_per_ws_tuning_<ts>.json`.
"""
from __future__ import annotations
import argparse
import glob
import json
import math
import os
import sys
import datetime
from typing import Dict, Tuple

import csv

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
STORE_DIR = os.path.join(ROOT, 'models_store')


def find_latest_sample() -> str:
    pattern = os.path.join(STORE_DIR, 'per_ws_playbyplay_sample_*.json')
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f'No sample JSON found matching {pattern}')
    files.sort()
    return files[-1]


def load_sample(path: str) -> Dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_canonical_csv(path: str) -> Dict[Tuple[str, str], Dict[str, float]]:
    out = {}
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            key = (r['player'].strip(), r['season'].strip())
            out[key] = {'PER': float(r['PER']), 'WS': float(r['WS'])}
    return out


def default_canonical_mapping() -> Dict[Tuple[str, str], Dict[str, float]]:
    # These are placeholder canonical targets used only for offline tuning/demo.
    # Replace by providing a real `--canonical-csv` file.
    mapping = {
        ("Stephen Curry", "2024-25"): {"PER": 26.0, "WS": 11.0},
        ("Stephen Curry", "2023-24"): {"PER": 27.0, "WS": 12.0},
        ("Stephen Curry", "2022-23"): {"PER": 28.0, "WS": 11.5},
        ("Nikola Jokic", "2024-25"): {"PER": 31.0, "WS": 20.0},
        ("Nikola Jokic", "2023-24"): {"PER": 30.0, "WS": 19.0},
        ("Nikola Jokic", "2022-23"): {"PER": 30.0, "WS": 19.0},
        ("Luka Doncic", "2024-25"): {"PER": 29.0, "WS": 18.0},
        ("Luka Doncic", "2023-24"): {"PER": 31.0, "WS": 22.0},
        ("Luka Doncic", "2022-23"): {"PER": 30.0, "WS": 17.0},
    }
    return mapping


def gather_pairs(sample: Dict, canonical_map: Dict[Tuple[str, str], Dict[str, float]]) -> Tuple[list, list, list]:
    per_ests = []
    ws_ests = []
    rows = []
    for player, pdata in sample.items():
        ests = pdata.get('estimates', {})
        for season, svals in ests.items():
            proto = svals.get('estimates', {})
            per_e = float(proto.get('PER_est', math.nan))
            ws_e = float(proto.get('WS_est', math.nan))
            key = (player, season)
            canonical = canonical_map.get(key)
            if canonical is None:
                continue
            per_c = float(canonical['PER'])
            ws_c = float(canonical['WS'])
            per_ests.append((per_e, per_c))
            ws_ests.append((ws_e, ws_c))
            rows.append({'player': player, 'season': season, 'PER_est': per_e, 'PER_can': per_c, 'WS_est': ws_e, 'WS_can': ws_c})
    return per_ests, ws_ests, rows


def fit_scale(ests_pairs):
    # Fit single multiplier a to minimize sum (a*est - can)^2
    num = 0.0
    den = 0.0
    for est, can in ests_pairs:
        num += est * can
        den += est * est
    if den == 0:
        return 1.0
    return num / den


def rmse(pairs, scale=1.0):
    n = 0
    s = 0.0
    for est, can in pairs:
        diff = scale * est - can
        s += diff * diff
        n += 1
    return math.sqrt(s / n) if n else float('nan')


def write_report(rows, per_scale, ws_scale, sample_path):
    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out_json = os.path.join(STORE_DIR, f'compare_per_ws_tuning_{ts}.json')
    out_csv = os.path.join(STORE_DIR, f'compare_per_ws_tuning_{ts}.csv')
    report = {'sample_path': sample_path, 'per_scale': per_scale, 'ws_scale': ws_scale, 'rows': rows}
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    # CSV
    with open(out_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['player', 'season', 'PER_est', 'PER_can', 'PER_est_scaled', 'PER_diff', 'WS_est', 'WS_can', 'WS_est_scaled', 'WS_diff'])
        writer.writeheader()
        for r in rows:
            per_scaled = r['PER_est'] * per_scale
            ws_scaled = r['WS_est'] * ws_scale
            writer.writerow({'player': r['player'], 'season': r['season'], 'PER_est': r['PER_est'], 'PER_can': r['PER_can'], 'PER_est_scaled': per_scaled, 'PER_diff': per_scaled - r['PER_can'], 'WS_est': r['WS_est'], 'WS_can': r['WS_can'], 'WS_est_scaled': ws_scaled, 'WS_diff': ws_scaled - r['WS_can']})
    return out_json, out_csv


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--canonical-csv', help='Path to CSV with player,season,PER,WS')
    parser.add_argument('--use-defaults', action='store_true', help='Use built-in canonical mapping for demo/tuning')
    args = parser.parse_args(argv)

    try:
        sample_path = find_latest_sample()
    except FileNotFoundError as e:
        print(str(e))
        sys.exit(1)

    sample = load_sample(sample_path)

    canonical_map = {}
    if args.canonical_csv:
        canonical_map = load_canonical_csv(args.canonical_csv)
    elif args.use_defaults:
        canonical_map = default_canonical_mapping()
    else:
        print('No canonical CSV provided and --use-defaults not set. Provide --canonical-csv or --use-defaults to run.')
        sys.exit(1)

    per_pairs, ws_pairs, rows = gather_pairs(sample, canonical_map)
    if not rows:
        print('No overlapping player-season pairs found between sample and canonical mapping.')
        sys.exit(1)

    per_scale = fit_scale(per_pairs)
    ws_scale = fit_scale(ws_pairs)

    per_rmse_before = rmse(per_pairs, scale=1.0)
    per_rmse_after = rmse(per_pairs, scale=per_scale)
    ws_rmse_before = rmse(ws_pairs, scale=1.0)
    ws_rmse_after = rmse(ws_pairs, scale=ws_scale)

    out_json, out_csv = write_report(rows, per_scale, ws_scale, sample_path)

    print('Wrote report:', out_json)
    print('Wrote CSV   :', out_csv)
    print('PER scale   :', per_scale)
    print('PER RMSE before/after :', per_rmse_before, per_rmse_after)
    print('WS scale    :', ws_scale)
    print('WS RMSE before/after  :', ws_rmse_before, ws_rmse_after)


if __name__ == '__main__':
    main()
