import datetime
import json
import os
import uuid
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from .training_data_service import export_dataset_with_version
from .. import db as _db

try:
    from sqlalchemy import create_engine, text
except Exception:
    create_engine = None


def _make_sync_db_url(async_url: str) -> Optional[str]:
    if not async_url:
        return None
    # convert obvious async variants to sync driver
    if async_url.startswith('sqlite+aiosqlite'):
        return async_url.replace('sqlite+aiosqlite', 'sqlite')
    # postgres asyncpg -> psycopg2 by stripping +asyncpg
    if '+asyncpg' in async_url:
        return async_url.replace('+asyncpg', '')
    return async_url


def create_dataset_version(name: str, seasons: str, df_train: pd.DataFrame, df_val: pd.DataFrame, df_test: pd.DataFrame, output_dir: str = 'backend/data/datasets', notes: Optional[str] = None) -> Dict:
    """Write train/val/test datasets to disk (Parquet preferred) and persist a dataset_versions metadata row when DB available.

    Returns manifest metadata dict.
    """
    version = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    uid = uuid.uuid4().hex[:8]
    base_name = name
    target_base = Path(output_dir)
    target_base.mkdir(parents=True, exist_ok=True)
    dir_name = f"{base_name}_v{version}_{uid}"
    target = target_base / dir_name
    target.mkdir(parents=True, exist_ok=False)

    manifest = {
        'name': base_name,
        'version': version,
        'uid': uid,
        'created_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'seasons': seasons,
        'rows_train': int(len(df_train)),
        'rows_val': int(len(df_val)),
        'rows_test': int(len(df_test)),
    }

    # write files using export helper
    m_train = export_dataset_with_version(df_train, None, output_dir=str(target), name=f'{base_name}_train', version=version)
    m_val = export_dataset_with_version(df_val, None, output_dir=str(target), name=f'{base_name}_val', version=version)
    m_test = export_dataset_with_version(df_test, None, output_dir=str(target), name=f'{base_name}_test', version=version)

    manifest['parts'] = {'train': m_train, 'val': m_val, 'test': m_test}

    manifest_path = target / 'dataset_manifest.json'
    with open(manifest_path, 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, indent=2, default=str)

    # attempt to persist metadata to DB table `dataset_versions` if available
    db_url = getattr(_db, 'DATABASE_URL', None)
    sync_url = _make_sync_db_url(db_url or '')
    if sync_url and create_engine is not None:
        try:
            engine = create_engine(sync_url)
            with engine.begin() as conn:
                insert_sql = text(
                    """
                    INSERT INTO dataset_versions (version_id, created_at, git_sha, seasons, rows_train, rows_val, rows_test, uid, manifest, notes)
                    VALUES (:version_id, :created_at, :git_sha, :seasons, :rows_train, :rows_val, :rows_test, :uid, :manifest::json, :notes)
                    RETURNING id
                    """
                )
                params = {
                    'version_id': version,
                    'created_at': manifest['created_at'],
                    'git_sha': os.environ.get('GIT_SHA') or os.environ.get('CI_COMMIT_SHA') or None,
                    'seasons': seasons,
                    'rows_train': manifest['rows_train'],
                    'rows_val': manifest['rows_val'],
                    'rows_test': manifest['rows_test'],
                    'uid': uid,
                    'manifest': json.dumps(manifest),
                    'notes': notes,
                }
                try:
                    res = conn.execute(insert_sql, params)
                    # consume returned id if present
                    _ = res.fetchone() if res is not None else None
                except Exception:
                    # best-effort: continue without failing if DB insert not possible
                    pass
        except Exception:
            pass

    return {'manifest': str(manifest_path), 'target_dir': str(target), 'metadata': manifest}
