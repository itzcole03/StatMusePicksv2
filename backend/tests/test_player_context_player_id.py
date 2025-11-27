from fastapi.testclient import TestClient

import backend.main as main_mod
from backend.main import app


def test_player_context_with_player_id(monkeypatch):
    # Simulate nba_stats_client returning a player id and fetch by id path
    sample_recent = [
        {
            "date": "2025-11-05",
            "statValue": 28,
            "opponentTeamId": "BOS",
            "opponentDefRating": 105.0,
        },
    ]

    class DummyClient:
        @staticmethod
        def find_player_id_by_name(name):
            return 2544

        @staticmethod
        def find_player_id(name):
            return 2544

        @staticmethod
        def fetch_recent_games_by_id(pid, limit=8):
            assert pid == 2544
            return sample_recent

    monkeypatch.setattr(main_mod, "nba_stats_client", DummyClient)

    client = TestClient(app)
    resp = client.get("/api/player_context?player_name=LeBron%20James&limit=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["player_id"] == 2544
    assert len(data["recentGames"]) == 1
