import os
import tempfile
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def test_team_stats_aggregation_tmp_db(monkeypatch):
    # Create a temporary SQLite DB file
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "test.db")
        url = f"sqlite:///{db_path}"
        # Ensure the ingestion code uses this DATABASE_URL
        monkeypatch.setenv("DATABASE_URL", url)

        # Import Base and models and create tables in the test DB
        from backend.db import Base

        engine = create_engine(url, future=True)
        Base.metadata.create_all(engine)

        # Prepare normalized games for team LAL (one home, one away)
        games = [
            {
                "game_date": datetime(2025, 11, 1),
                "home_team": "LAL",
                "away_team": "BOS",
                "home_score": 110,
                "away_score": 100,
            },
            {
                "game_date": datetime(2025, 11, 5),
                "home_team": "GSW",
                "away_team": "LAL",
                "home_score": 120,
                "away_score": 115,
            },
        ]

        # Call the ingestion function to insert games and compute aggregates
        from backend.services.data_ingestion_service import update_team_stats

        updated = update_team_stats(games)
        assert updated >= 2

        # Open a session against the same DB and verify TeamStat
        from backend.models import TeamStat

        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            ts = session.query(TeamStat).filter_by(team="LAL").first()
            assert ts is not None
            # season is the year string
            assert ts.season == "2025"
            # pts_for_avg = (110 + 115) / 2 = 112.5
            assert round(ts.pts_for_avg, 3) == 112.5
            # pts_against_avg = (100 + 120) / 2 = 110.0
            assert round(ts.pts_against_avg, 3) == 110.0
            assert ts.games_count == 2
        finally:
            session.close()
            try:
                engine.dispose()
            except Exception:
                pass
