r"""Dump per-player feature CSVs (including advanced + LLM features) for inspection.

Writes `backend/models_store/player_features_<Player>_<timestamp>.csv` for each player.

Usage example (PowerShell from repo root):

    $env:PYTHONPATH='.'; & .\.venv\Scripts\python.exe backend\scripts\dump_player_features.py --players "Stephen Curry,LeBron James" --min-games 1
"""
from __future__ import annotations

import argparse
import datetime
import logging
import os
from typing import List

import pandas as pd

from backend.services import training_data_service
from backend.scripts.retrain_with_advanced_features import augment_with_llm

logger = logging.getLogger("dump_player_features")
logging.basicConfig(level=logging.INFO)


def safe_name(name: str) -> str:
    return name.replace(' ', '_').replace('/', '_')


def dump_player(player: str, min_games: int = 1, fetch_limit: int = 500, seasons: str = None, out_dir: str = 'backend/models_store') -> str:
    try:
        seasons_list = [s.strip() for s in seasons.split(',')] if seasons else None
        df = training_data_service.generate_training_data(player, min_games=min_games, fetch_limit=fetch_limit, seasons=seasons_list)
    except Exception:
        logger.exception("Failed to generate training data for %s", player)
        return ""

    # augment with deterministic LLM features
    try:
        df_aug = augment_with_llm(df, player)
    except Exception:
        logger.exception("LLM augmentation failed for %s", player)
        df_aug = df.copy()
        for c in ('injury_sentiment', 'morale_score', 'motivation'):
            df_aug[c] = 0.0

    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    fname = f"player_features_{safe_name(player)}_{ts}.csv"
    path = os.path.join(out_dir, fname)
    try:
        df_aug.to_csv(path, index=False)
    except Exception:
        logger.exception("Failed to write CSV for %s", player)
        return ""

    logger.info("Wrote features for %s -> %s", player, path)
    return path


def main(players: List[str], min_games: int = 1, fetch_limit: int = 500, seasons: str = None):
    written = []
    for p in players:
        logger.info("Dumping features for %s", p)
        out = dump_player(p, min_games=min_games, fetch_limit=fetch_limit, seasons=seasons)
        if out:
            written.append(out)

    if written:
        print("Wrote files:\n" + '\n'.join(written))
    else:
        print("No feature files written; check logs.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Dump per-player feature CSVs')
    parser.add_argument('--players', default=None, help='Comma-separated player list')
    parser.add_argument('--min-games', type=int, default=1)
    parser.add_argument('--fetch-limit', type=int, default=500, help='Fetch limit passed to training_data_service')
    parser.add_argument('--seasons', default=None, help='Comma-separated seasons to fetch (e.g. "2024-25,2023-24")')
    args = parser.parse_args()

    default_players = [
        'LeBron James',
        'Stephen Curry',
        'Luka Doncic',
        'Kevin Durant',
        'Jayson Tatum',
    ]

    if args.players:
        players = [p.strip() for p in args.players.split(',') if p.strip()]
    else:
        players = default_players

    main(players, min_games=args.min_games, fetch_limit=args.fetch_limit, seasons=args.seasons)
