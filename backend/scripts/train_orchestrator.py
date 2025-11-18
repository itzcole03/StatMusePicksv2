#!/usr/bin/env python3
"""Train orchestrator: iterate players, build datasets, train per-player models.

Behavior:
- Query `players` and `player_stats` from the sync DB and select players
  with at least `--min-games` records for the requested stat.
- For each player, call `generate_training_data` to build a DataFrame (best-effort).
- Apply chronological split, train on the training split, persist model via
  `ModelRegistry.save_model`, and optionally export the training dataset.

This script is safe to run from CI or locally. It is best-effort: failures
for individual players are logged and do not abort the whole run.
"""
from __future__ import annotations
import os
import argparse
import logging
import datetime
from typing import List, Optional

import pandas as pd

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')


def _sync_db_url(raw: Optional[str]) -> str:
    if not raw:
        return "sqlite:///./dev.db"
    if "${" in raw:
        return "sqlite:///./dev.db"
    sync = raw.replace("+aiosqlite", "")
    sync = sync.replace("+asyncpg", "")
    sync = sync.replace("+asyncmy", "")
    return sync


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--min-games', type=int, default=50, help='Minimum historical games to consider training')
    p.add_argument('--stat', default='points', help='Stat type (points/assists/rebounds)')
    p.add_argument('--limit', type=int, default=500, help='Fetch limit passed to generate_training_data')
    p.add_argument('--seasons', default=None, help='Comma-separated seasons to pass to generator (e.g. 2019-20,2020-21)')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--export-train', action='store_true', help='Export train split via export_dataset_with_version')
    args = p.parse_args()

    raw_db = os.environ.get('DATABASE_URL')
    sync_url = _sync_db_url(raw_db)

    # local imports to avoid heavy deps during module import
    from sqlalchemy import create_engine, func
    from sqlalchemy.orm import sessionmaker
    from backend.models import Player, PlayerStat
    from backend.services import training_data_service as tds
    from backend.services import training_pipeline as tp
    from backend.services.model_registry import ModelRegistry

    engine = create_engine(sync_url, future=True)
    Session = sessionmaker(bind=engine)
    session = Session()

    seasons = None
    if args.seasons:
        seasons = [s.strip() for s in args.seasons.split(',') if s.strip()]

    # Query players with counts for the requested stat
    logger.info('Querying players with >= %d games for stat=%s', args.min_games, args.stat)
    try:
        q = session.query(Player.id, Player.name, func.count(PlayerStat.id).label('game_count')).join(PlayerStat).filter(PlayerStat.stat_type == args.stat).group_by(Player.id)
        candidates = [r for r in q.all() if int(r.game_count) >= args.min_games]
    except Exception:
        logger.exception('Failed to query DB for player counts; falling back to all players')
        candidates = session.query(Player.id, Player.name).all()

    logger.info('Found %d candidate players for training', len(candidates))

    registry = ModelRegistry()
    results = []
    for rec in candidates:
        player_name = rec.name if hasattr(rec, 'name') else rec[1]
        try:
            logger.info('Building dataset for %s', player_name)
            df = tds.generate_training_data(player_name, stat=args.stat, min_games=20, fetch_limit=args.limit, seasons=seasons)
            if df is None or len(df) < 10:
                logger.warning('Not enough rows for %s after generation: %s', player_name, len(df) if df is not None else 0)
                continue

            # Split chronologically
            train_df, val_df, test_df = tds.chronological_split_by_ratio(df, date_col='game_date')
            if len(train_df) < 5:
                logger.warning('Train split too small for %s, skipping', player_name)
                continue

            if args.dry_run:
                logger.info('Dry run: would train model for %s (rows=%d)', player_name, len(train_df))
                results.append({'player': player_name, 'status': 'dry-run', 'rows': len(train_df)})
                continue

            # Train on train_df (expects 'target' column)
            model = tp.train_player_model(train_df, target_col='target')

            # Save model artifact via ModelRegistry
            version = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
            registry.save_model(player_name, model, version=version, notes=f'trained {version} rows={len(train_df)}')

            # Fit a calibrator on the validation set (best-effort). Use isotonic by default.
            try:
                from backend.services.calibration_service import CalibrationService

                if val_df is not None and len(val_df) >= 3:
                    # Prepare features and target for validation
                    X_val = val_df.drop(columns=['target'], errors='ignore')
                    # numeric-only
                    X_val = X_val.select_dtypes(include=['number']).fillna(0)
                    # Ensure column alignment: use same feature columns model was trained on
                    try:
                        y_val = val_df['target'].astype(float).to_numpy()
                        # Predict using model; some regressors expect 2D input
                        try:
                            y_pred_val = model.predict(X_val)
                        except Exception:
                            # fallback: try numeric conversion
                            y_pred_val = model.predict(X_val.values)

                        calib_svc = CalibrationService()
                        # Fit and persist calibrator
                        cal_info = calib_svc.fit_and_save(player_name, y_true=y_val, y_pred=y_pred_val, method='isotonic')
                        logger.info('Calibration fitted for %s: before=%s after=%s', player_name, cal_info.get('before'), cal_info.get('after'))
                    except Exception:
                        logger.exception('Failed to fit calibrator for %s', player_name)
                else:
                    logger.info('Not enough validation rows to fit calibrator for %s', player_name)
            except Exception:
                logger.exception('CalibrationService not available or failed for %s', player_name)

            # Optionally export train dataset for audit/consumption
            if args.export_train:
                manifest = tds.export_dataset_with_version(train_df, y=None, output_dir='datasets', name=player_name.replace(' ', '_') + '_train', version=version)
                logger.info('Exported train dataset for %s: %s', player_name, manifest.get('files', {}))

            results.append({'player': player_name, 'status': 'trained', 'rows': len(train_df), 'version': version})
        except Exception:
            logger.exception('Failed to train for player %s', player_name)
            results.append({'player': player_name, 'status': 'failed'})

    # Summary
    logger.info('Orchestration completed for %d players', len(results))
    for r in results:
        logger.info('Player %s -> %s', r.get('player'), r.get('status'))

    try:
        session.close()
    except Exception:
        pass


if __name__ == '__main__':
    main()
