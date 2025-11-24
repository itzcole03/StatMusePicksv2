"""Small tuner: grid-search PER_SCALE, WS_SCALE, ADV_PROXY_DECAY against canonical targets.

Writes tuning report JSON to `backend/models_store/tuning_report_<ts>.json`.

Usage:
    $env:PYTHONPATH='.'; & .\.venv\Scripts\python.exe backend\scripts\tune_per_ws_and_decay.py
"""
from __future__ import annotations

import datetime
import json
import math
import os
from itertools import product
from pathlib import Path

import pandas as pd
import numpy as np

from backend.services import per_ws_from_playbyplay as perws
from backend.services import nba_stats_client

CANON = Path('backend/data/canonical_per_ws.csv')
OUT_DIR = Path('backend/models_store')
OUT_DIR.mkdir(parents=True, exist_ok=True)

# small grids
PER_GRID = [0.2, 0.3, 0.34, 0.4]
WS_GRID = [0.2, 0.3, 0.31, 0.4]
DECAY_GRID = [0.6, 0.7, 0.8, 0.9]

# load canonical
cf = pd.read_csv(CANON)
# group by player-season
canon_map = {(r['player'], str(r['season'])): (float(r['PER']), float(r['WS'])) for _, r in cf.iterrows()}

# helper: compute season-level estimates from play logs using perws functions
def compute_estimates_for_player_season(player_name, season):
    pid = nba_stats_client.find_player_id_by_name(player_name)
    if not pid:
        return None
    games = nba_stats_client.fetch_recent_games(pid, limit=500, season=season)
    if not games:
        return None
    agg = perws.aggregate_season_games(games)
    est = perws.compute_per_ws_from_aggregates(agg)
    return est

results = []
for p_scale, w_scale, decay in product(PER_GRID, WS_GRID, DECAY_GRID):
    # set temporary scales
    perws.PER_SCALE = float(p_scale)
    perws.WS_SCALE = float(w_scale)
    # store decay temporarily in env for training_data_service to pick up if used
    os.environ['ADV_PROXY_DECAY'] = str(decay)

    per_errors = []
    ws_errors = []
    count = 0
    for (player, season), (per_t, ws_t) in canon_map.items():
        est = compute_estimates_for_player_season(player, season)
        if not est:
            continue
        per_e = est.get('PER_est')
        ws_e = est.get('WS_est')
        if per_e is None or ws_e is None:
            continue
        per_errors.append((per_e - per_t) ** 2)
        ws_errors.append((ws_e - ws_t) ** 2)
        count += 1

    if count == 0:
        continue

    per_rmse = math.sqrt(sum(per_errors) / len(per_errors)) if per_errors else float('nan')
    ws_rmse = math.sqrt(sum(ws_errors) / len(ws_errors)) if ws_errors else float('nan')
    combined = per_rmse + ws_rmse
    results.append({'PER_SCALE': p_scale, 'WS_SCALE': w_scale, 'DECAY': decay, 'per_rmse': per_rmse, 'ws_rmse': ws_rmse, 'sum_rmse': combined, 'count': count})

# sort and write
results_sorted = sorted(results, key=lambda r: r['sum_rmse'])
now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
out_path = OUT_DIR / f'tuning_report_{now}.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump({'grid': results_sorted}, f, indent=2)
print('Wrote tuning report to', out_path)

# print top 3
for r in results_sorted[:3]:
    print(r)

print('DONE')
