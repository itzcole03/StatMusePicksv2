"""Create dataset_versions table in the configured DATABASE_URL (sqlite or postgres).

Usage:
  Set `DATABASE_URL` env var (falls back to repo dev.db) then:
    python scripts/create_dataset_versions_table.py
"""
import os
from sqlalchemy import create_engine, text

db_url = os.environ.get('DATABASE_URL') or 'sqlite:///dev.db'
# normalize async sqlite URL if present
if db_url.startswith('sqlite+aiosqlite'):
    sync_url = db_url.replace('sqlite+aiosqlite', 'sqlite')
elif '+asyncpg' in db_url:
    sync_url = db_url.replace('+asyncpg', '')
else:
    sync_url = db_url

print('Using DB URL:', sync_url)
engine = create_engine(sync_url)
create_sql = '''
CREATE TABLE IF NOT EXISTS dataset_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id TEXT NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    git_sha TEXT,
    seasons TEXT,
    rows_train INTEGER,
    rows_val INTEGER,
    rows_test INTEGER,
    uid TEXT,
    manifest TEXT,
    notes TEXT
);
'''
with engine.begin() as conn:
    conn.execute(text(create_sql))
print('Ensured dataset_versions table exists')
