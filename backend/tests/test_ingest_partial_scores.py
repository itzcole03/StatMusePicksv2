import os
import tempfile
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.services.data_ingestion_service import update_team_stats


def test_ingest_partial_scores_update(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "test.db")
        url = f"sqlite:///{db_path}"
        monkeypatch.setenv("DATABASE_URL", url)

        # create tables
        from backend.db import Base
        engine = create_engine(url, future=True)
        Base.metadata.create_all(engine)

        # initial ingest: one game with missing away_score
        game = {"game_date": datetime(2025, 11, 20), "home_team": "LAL", "away_team": "BOS", "home_score": 110}
        updated1 = update_team_stats([game])
        assert updated1 >= 1

        # now provide the away_score in a follow-up ingest (should update existing game)
        game_update = {"game_date": datetime(2025, 11, 20), "home_team": "LAL", "away_team": "BOS", "home_score": 110, "away_score": 105}
        updated2 = update_team_stats([game_update])
        # updated2 should reflect that an existing row was changed (>=1)
        assert updated2 >= 1

        # verify stored values
        from backend.models import Game
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            g = session.query(Game).filter_by(home_team="LAL", away_team="BOS").first()
            assert g is not None
            assert g.home_score == 110
            assert g.away_score == 105
        finally:
            session.close()
            try:
                engine.dispose()
            except Exception:
                pass
