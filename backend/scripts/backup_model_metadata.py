"""Backup `model_metadata` table to CSV using a sync SQLAlchemy engine.

Usage:
    python backend/scripts/backup_model_metadata.py [--db-url DB_URL] [--out PATH]

If `--db-url` omitted uses `DATABASE_URL` env var or falls back to `sqlite:///./dev.db`.
"""
from __future__ import annotations
import argparse
import os
from sqlalchemy import create_engine
import pandas as pd


def _sync_db_url(raw: str | None) -> str:
    if not raw:
        return "sqlite:///./dev.db"
    if "${" in raw:
        return "sqlite:///./dev.db"
    sync = raw
    sync = sync.replace("+aiosqlite", "")
    sync = sync.replace("+asyncpg", "")
    sync = sync.replace("+asyncmy", "")
    return sync


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db-url", help="Database URL (sync or async); if omitted uses $DATABASE_URL or sqlite dev.db")
    p.add_argument("--out", default="model_metadata_backup.csv", help="Output CSV path")
    args = p.parse_args()

    raw = args.db_url or os.environ.get('DATABASE_URL')
    sync_url = _sync_db_url(raw)
    engine = create_engine(sync_url, future=True)
    try:
        df = pd.read_sql_table('model_metadata', engine)
    except Exception as exc:
        print('Failed to read model_metadata:', exc)
        raise
    df.to_csv(args.out, index=False)
    print(f'Wrote backup to {args.out}')


if __name__ == '__main__':
    main()
