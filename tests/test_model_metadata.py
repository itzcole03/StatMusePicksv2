import os
import sys
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path.cwd()


def test_model_metadata_insert(tmp_path):
    # Use isolated DB for this test
    db_file = tmp_path / "mm.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_file}"

    # Run alembic migrations to create tables
    subprocess.run([sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"], check=True, env=env, cwd=str(ROOT))

    # Run the training script which now uses ModelRegistry.save_model
    subprocess.run([sys.executable, "backend/scripts/train_example.py"], check=True, env=env, cwd=str(ROOT))

    # Query the model_metadata table via sqlite (sync URL)
    sync_url = str(db_file)
    import sqlite3
    conn = sqlite3.connect(sync_url)
    cur = conn.cursor()
    cur.execute("SELECT name, version, path, notes FROM model_metadata ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()

    assert row is not None, "Expected a row in model_metadata"
    name, version, path, notes = row
    assert name == 'synthetic_player'
    assert version == 'v0.1-synthetic'
    assert 'synthetic_player.pkl' in path
    assert 'Synthetic training run' in (notes or '')
