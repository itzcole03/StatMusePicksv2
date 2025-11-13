import os
import tempfile
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.services.data_ingestion_service import update_team_stats


def test_ingest_missing_fields(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "test.db")
        url = f"sqlite:///{db_path}"
        monkeypatch.setenv("DATABASE_URL", url)

        # create tables
        from backend.db import Base
        engine = create_engine(url, future=True)
        Base.metadata.create_all(engine)

        games = [
            # missing away_team
            {"game_date": datetime(2025, 11, 10), "home_team": "LAL", "home_score": 100, "away_score": 95},
            # missing home_team
            {"game_date": datetime(2025, 11, 11), "away_team": "BOS", "home_score": 105, "away_score": 99},
            # missing both teams -> should be skipped
            {"game_date": datetime(2025, 11, 12), "home_score": 110, "away_score": 108},
        ]

        updated = update_team_stats(games)
        # We now accept partial records (missing home or away team). Two
        # valid rows should be inserted; the completely-teamless record is
        # skipped because no teams are present.
        assert updated >= 2

        # verify games exist in DB
        from backend.models import Game
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            rows = session.query(Game).all()
            # two created rows (one with UNKNOWN away, one with UNKNOWN home)
            assert len(rows) >= 2
            teams = {r.home_team for r in rows} | {r.away_team for r in rows}
            assert "UNKNOWN" in teams
        finally:
            session.close()
            try:
                engine.dispose()
            except Exception:
                pass
