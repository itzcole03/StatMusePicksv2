#!/usr/bin/env python3
"""Generate a dataset version from current NBA roster players.

Fetches roster via `backend.services.nba_stats_client.fetch_all_players()` or
`CommonTeamRoster`, resolves player IDs, generates per-player training rows
via `generate_training_data(pid=...)`, concatenates results, splits
per-player time-based train/val/test, and writes a dataset manifest via
`create_dataset_version`.

This is intended for interactive dev use; it may take several minutes.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import List

import os
import sys

# ensure repo root on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.services import training_data_service as tds
from backend.services import dataset_versioning as dv
from backend.services.nba_stats_client import fetch_all_players, find_player_id_by_name
from backend.scripts.train_orchestrator_roster import fetch_roster_names
import time
import multiprocessing as mp
from pathlib import Path

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    lvl = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=lvl, format='%(asctime)s %(levelname)s %(message)s')


def _per_player_worker(q, name, pid, seasons, min_games, fetch_limit):
    """Top-level worker for multiprocessing (must be picklable on Windows)."""
    try:
        df = tds.generate_training_data(name, stat='points', min_games=min_games, fetch_limit=fetch_limit, seasons=seasons, pid=int(pid))
        df['player_id'] = int(pid)
        q.put({'ok': True, 'df': df})
    except Exception as e:
        q.put({'ok': False, 'error': str(e)})


def build_dataset_for_roster(seasons: List[str], min_games: int = 5, fetch_limit: int = 500, progress_file: str | None = None, resume: bool = False) -> dict:
    rows = []
    players = []
    processed = set()
    progress_path = Path(progress_file) if progress_file else None
    if resume and progress_path and progress_path.exists():
        try:
            data = json.loads(progress_path.read_text())
            processed = set(data.get('processed', []))
            logger.info('Resuming dataset generation; %d players already processed', len(processed))
        except Exception:
            logger.info('Failed to read progress file; starting from scratch')

    # fetch current-season roster names
    roster = fetch_roster_names() or []
    total = len(roster)
    for idx, name in enumerate(roster, start=1):
        if name in processed:
            logger.debug('Skipping %s (already processed)', name)
            continue

        pid = None
        # resolve player id with a small retry loop to handle transient API hiccups
        for attempt in range(3):
            try:
                pid = find_player_id_by_name(name)
                break
            except Exception as exc:
                logger.debug('find_player_id_by_name failed for %s (attempt %d): %s', name, attempt + 1, exc)
                time.sleep(0.5 * (attempt + 1))

        if not name or not pid:
            logger.info('Skipping roster name without resolvable id: %s (%d/%d)', name, idx, total)
            if progress_path:
                processed.add(name)
                progress_path.write_text(json.dumps({'processed': list(processed)}, indent=2))
            continue

        # generate training rows with retries and graceful interrupt handling

        success = False
        for attempt in range(3):
            q = mp.Queue()
            p = mp.Process(target=_per_player_worker, args=(q, name, pid, seasons, min_games, fetch_limit))
            p.start()
            p.join(timeout=getattr(build_dataset_for_roster, '_per_player_timeout', 60))
            if p.is_alive():
                logger.warning('Player generation timed out for %s (attempt %d)', name, attempt + 1)
                try:
                    p.terminate()
                except Exception:
                    logger.debug('Failed to terminate process for %s', name)
                p.join(1)
                # consume queue if possible
                try:
                    while not q.empty():
                        q.get_nowait()
                except Exception:
                    pass
                time.sleep(0.5 * (attempt + 1))
                continue

            # process finished within timeout
            try:
                res = q.get_nowait()
            except Exception as e:
                logger.debug('No result in queue for %s: %s', name, e)
                res = {'ok': False, 'error': 'no-result'}

            if res.get('ok'):
                df = res.get('df')
                rows.append(df)
                players.append(name)
                logger.info('Generated %d rows for %s (%s) (%d/%d)', len(df), name, pid, idx, total)
                success = True
                break
            else:
                logger.debug('Attempt %d failed for %s: %s', attempt + 1, name, res.get('error'))
                time.sleep(1.0 * (attempt + 1))

        if not success:
            logger.info('Skipping %s: failed after retries', name)

        # mark processed and persist progress
        if progress_path:
            processed.add(name)
            try:
                progress_path.write_text(json.dumps({'processed': list(processed)}, indent=2))
            except Exception:
                logger.debug('Failed writing progress file %s', progress_path)

        # polite sleep to avoid hitting rate limits
        time.sleep(0.25)

    # attach default per-player timeout attribute for external control
    setattr(build_dataset_for_roster, '_per_player_timeout', 60)

    if not rows:
        raise SystemExit('No training rows generated for any roster players')

    import pandas as pd
    combined = pd.concat(rows, ignore_index=True)

    # ensure numeric player_id present for robust matching downstream
    if 'player_id' not in combined.columns:
        logger.info('player_id column missing from generated rows; attempting to resolve via name')
        unique_players = combined['player'].astype(str).unique().tolist()
        name_to_id = {}
        for pn in unique_players:
            try:
                pid = find_player_id_by_name(pn)
            except Exception:
                pid = None
            if pid:
                name_to_id[pn] = int(pid)
        # map where possible, else leave null and drop those rows later
        combined['player_id'] = combined['player'].map(lambda x: name_to_id.get(str(x)))

    # drop rows without resolved player_id (avoid ambiguous name-only rows)
    before = len(combined)
    combined = combined[combined['player_id'].notnull()].copy()
    after = len(combined)
    if after < before:
        logger.info('Dropped %d rows without resolved player_id', before - after)

    # ensure integer dtype
    try:
        combined['player_id'] = combined['player_id'].astype(int)
    except Exception:
        combined['player_id'] = combined['player_id'].apply(lambda x: int(x) if x is not None else None)

    # split per-player time-based using numeric id to avoid name collisions
    train_df, val_df, test_df = tds.per_player_time_split(combined, player_col='player_id', date_col='game_date', train_frac=0.7, val_frac=0.15, test_frac=0.15)

    manifest_info = dv.create_dataset_version(name='points_dataset', seasons=','.join(seasons), df_train=train_df, df_val=val_df, df_test=test_df, output_dir='backend/data/datasets')

    # sanity-check: manifest parts should include player_id column
    try:
        mpath = Path(manifest_info['manifest'])
        m = json.loads(mpath.read_text())
        for split in ('train', 'val', 'test'):
            cols = m['parts'][split].get('columns') or []
            if 'player_id' not in cols:
                logger.warning('Exported manifest part %s missing player_id column; consider re-running with parquet engine available', split)
    except Exception:
        logger.debug('Failed to validate manifest columns')

    return manifest_info


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--seasons', default='2024-25', help='Comma-separated seasons (e.g. 2024-25)')
    p.add_argument('--min-games', type=int, default=5)
    p.add_argument('--fetch-limit', type=int, default=500)
    p.add_argument('--verbose', action='store_true', help='Enable debug logging')
    p.add_argument('--resume', action='store_true', help='Resume from previous progress file if present')
    p.add_argument('--progress-file', default='backend/models_store/dataset_generation_progress.json', help='Path to write progress/resume file')
    args = p.parse_args()
    setup_logging(verbose=getattr(args, 'verbose', False))
    seasons = [s.strip() for s in args.seasons.split(',') if s.strip()]
    info = build_dataset_for_roster(seasons, min_games=args.min_games, fetch_limit=args.fetch_limit, progress_file=args.progress_file, resume=args.resume)
    print('Wrote dataset manifest:', info)


if __name__ == '__main__':
    main()
