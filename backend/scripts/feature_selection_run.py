"""Run per-player feature selection for likely-active roster players.

Writes `backend/models_store/feature_selection_report.csv` and JSON.
"""
from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
from pathlib import Path
from time import time

import pandas as pd

from backend.services import training_data_service
from backend.services import feature_selection as fs

logger = logging.getLogger("feature_selection_run")
logging.basicConfig(level=logging.INFO)


def compute_last_n_seasons(n: int = 3) -> list:
    now = datetime.date.today()
    year = now.year
    if now.month >= 10:
        start_year = year
    else:
        start_year = year - 1
    seasons = [f"{start_year - i}-{str((start_year - i + 1) % 100).zfill(2)}" for i in range(0, n)]
    return seasons


def load_roster(path: str):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)


def main(min_games: int, out_csv: str, limit: int | None):
    seasons = compute_last_n_seasons(3)
    roster = load_roster('backend/data/roster_cache.json')

    players = [r.get('full_name') for r in roster if r.get('is_active') and r.get('full_name')]
    players = [p for p in players if p]
    if limit:
        players = players[:limit]

    results = []
    os.makedirs(Path(out_csv).parent, exist_ok=True)

    for idx, player in enumerate(players, start=1):
        logger.info("[%d/%d] Processing %s", idx, len(players), player)
        t0 = time()
        rec = {
            'player': player,
            'status': 'ok',
            'rows': 0,
            'num_features': 0,
            'corr_selected': None,
            'rfe_selected': None,
            'error': None,
            'duration_s': None,
            'seasons': ','.join(seasons),
        }
        try:
            df = training_data_service.generate_training_data(player, min_games=min_games, fetch_limit=500, seasons=seasons)
            rec['rows'] = int(len(df))
            # features exclude 'target'
            rec['num_features'] = int(len([c for c in df.columns if c != 'target']))

            try:
                corr = fs.select_by_correlation(df, target_col='target', thresh=0.01)
            except Exception as e:
                corr = []
                logger.exception('Correlation selection failed for %s', player)

            try:
                rfe = fs.rfe_select(df, target_col='target')
            except Exception as e:
                rfe = []
                logger.exception('RFE selection failed for %s', player)

            rec['corr_selected'] = json.dumps(corr)
            rec['rfe_selected'] = json.dumps(rfe)
        except Exception as e:
            rec['status'] = 'failed'
            rec['error'] = str(e)
        finally:
            rec['duration_s'] = round(time() - t0, 2)
            results.append(rec)

    df_out = pd.DataFrame(results)
    df_out.to_csv(out_csv, index=False)
    # also write JSON for ease of parsing
    with open(out_csv.replace('.csv', '.json'), 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    logger.info('Wrote feature selection report: %s', out_csv)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Per-player feature selection for active roster')
    parser.add_argument('--min-games', type=int, default=5)
    parser.add_argument('--out-csv', default='backend/models_store/feature_selection_report.csv')
    parser.add_argument('--limit', type=int, default=None, help='Optional limit on number of players to process')
    args = parser.parse_args()

    main(args.min_games, args.out_csv, args.limit)
