import json
from pathlib import Path
import shutil
import datetime
from typing import Optional, List


def register_manifest(manifest_path: str, registry_dir: str = 'backend/models_store/datasets') -> Optional[dict]:
    """Register an exported dataset (the directory containing `manifest.json`) into a central registry.

    Copies the dataset directory into `registry_dir/{name}/{version}_{uid}/` and
    updates `registry_dir/index.json` with a record for quick lookup.
    Returns the registered manifest dict with an added `_registry_path` key on success,
    or None on failure.
    """
    try:
        mp = Path(manifest_path)
        if not mp.exists():
            return None
        dataset_dir = mp.parent
        with open(mp, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        name = manifest.get('name', 'dataset')
        version = manifest.get('version', datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        uid = manifest.get('uid') or ''

        dest_root = Path(registry_dir)
        dest_root.mkdir(parents=True, exist_ok=True)
        dest_name_dir = dest_root / name
        dest_name_dir.mkdir(parents=True, exist_ok=True)

        dest_dir_name = f"{version}_{uid}" if uid else version
        dest_dir = dest_name_dir / dest_dir_name
        # avoid overwriting
        if dest_dir.exists():
            # if same content, just update index
            pass
        else:
            shutil.copytree(dataset_dir, dest_dir)

        # update manifest path to point to new location
        manifest['_registry_path'] = str(dest_dir)

        # update central index
        index_path = dest_root / 'index.json'
        index = []
        if index_path.exists():
            try:
                with open(index_path, 'r', encoding='utf-8') as f:
                    index = json.load(f) or []
            except Exception:
                index = []

        # remove any existing entry with same name+version+uid
        index = [e for e in index if not (e.get('name') == name and e.get('version') == version and e.get('uid') == uid)]
        entry = {
            'name': name,
            'version': version,
            'uid': uid,
            'created_at': manifest.get('created_at') or datetime.datetime.now(datetime.timezone.utc).isoformat() + 'Z',
            'rows': manifest.get('rows', 0),
            'columns': manifest.get('columns', []),
            '_registry_path': str(dest_dir)
        }
        index.append(entry)
        # sort by created_at
        try:
            index.sort(key=lambda x: x.get('created_at') or '')
        except Exception:
            pass

        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=2, default=str)

        return manifest
    except Exception:
        return None


def list_registered(name: Optional[str] = None, registry_dir: str = 'backend/models_store/datasets') -> List[dict]:
    idx = Path(registry_dir) / 'index.json'
    if not idx.exists():
        return []
    try:
        with open(idx, 'r', encoding='utf-8') as f:
            entries = json.load(f) or []
    except Exception:
        return []
    if name:
        return [e for e in entries if e.get('name') == name]
    return entries


def latest_registered(name: str, registry_dir: str = 'backend/models_store/datasets') -> Optional[dict]:
    entries = list_registered(name=name, registry_dir=registry_dir)
    if not entries:
        return None
    # assume sorted by created_at in list_registered
    return entries[-1]


def get_latest_dataset(name: str, registry_dir: str = 'backend/models_store/datasets') -> Optional[dict]:
    """Return the parsed manifest dict for the latest registered dataset with `name`.

    This reads the `manifest.json` file from the registry copy and returns its contents
    with an added `_registry_path` indicating where the files live.
    """
    latest = latest_registered(name=name, registry_dir=registry_dir)
    if not latest:
        return None
    manifest_path = Path(latest.get('_registry_path', '')) / 'manifest.json'
    if not manifest_path.exists():
        return latest
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            m = json.load(f)
        m['_registry_path'] = str(manifest_path.parent)
        return m
    except Exception:
        return latest
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
    version = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
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
        'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat() + 'Z',
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
