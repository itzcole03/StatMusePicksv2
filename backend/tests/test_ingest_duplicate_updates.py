import os
import tempfile
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.services.data_ingestion_service import update_team_stats


def test_ingest_duplicate_updates(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "test.db")
        url = f"sqlite:///{db_path}"
        monkeypatch.setenv("DATABASE_URL", url)

        # create tables
        from backend.db import Base
        engine = create_engine(url, future=True)
        Base.metadata.create_all(engine)

        game = {"game_date": datetime(2025, 11, 25), "home_team": "LAL", "away_team": "NYK", "home_score": 102, "away_score": 99}
        # first ingest
        updated1 = update_team_stats([game])
        # duplicate identical ingest should not create additional rows but may return 0
        updated2 = update_team_stats([game])

        from backend.models import Game
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            rows = session.query(Game).filter_by(home_team="LAL", away_team="NYK").all()
            # Only one game row should exist
            assert len(rows) == 1
        finally:
            session.close()
            try:
                engine.dispose()
            except Exception:
                pass
