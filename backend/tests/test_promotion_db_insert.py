import os
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, text


def test_promote_inserts_db_row(tmp_path, monkeypatch):
    # prepare temporary DB file
    db_file = tmp_path / "promotions.db"
    db_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    # create promotions table
    engine = create_engine(db_url, future=True)
    create_sql = """
    CREATE TABLE IF NOT EXISTS model_promotions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_name TEXT NOT NULL,
        version TEXT,
        promoted_by TEXT,
        promoted_at TIMESTAMP,
        notes TEXT
    );
    """
    with engine.begin() as conn:
        conn.execute(text(create_sql))

    # prepare registry and save a toy model entry
    from backend.services.model_registry import PlayerModelRegistry
    from sklearn.dummy import DummyRegressor
    import numpy as _np

    store_dir = tmp_path / "models_store"
    reg = PlayerModelRegistry(str(store_dir))

    m = DummyRegressor(strategy="constant", constant=1.0)
    m.fit(_np.zeros((1, 1)), [1.0])

    version = reg.save_model("Test Player", m, metadata={"notes": "test"})

    # call promote_model which should insert into the DB
    reg.promote_model("Test Player", version=version, promoted_by="tester", notes="promoted for test")

    # verify row exists
    with engine.connect() as conn:
        res = conn.execute(text("SELECT player_name, version, promoted_by, notes FROM model_promotions WHERE player_name = :p"), {"p": "Test Player"})
        rows = res.fetchall()

    assert len(rows) == 1
    row = rows[0]
    assert row[0] == "Test Player"
    assert row[1] == version
    assert row[2] == "tester"
    assert row[3] == "promoted for test"
