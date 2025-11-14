from fastapi.testclient import TestClient
import backend.main as main_mod
from backend.main import app


def test_player_context_dev_mock_env(monkeypatch):
    # The production code no longer fabricates deterministic recent games.
    # Instead, monkeypatch the `nba_stats_client` used by the endpoint so
    # tests explicitly control returned recentGames for deterministic behavior.
    sample_recent = [
        {"date": "2025-11-01", "statValue": 28, "opponentTeamId": "BOS", "opponentDefRating": 105.0, "opponentPace": 98.3},
        {"date": "2025-10-29", "statValue": 24, "opponentTeamId": "NYK", "opponentDefRating": 110.0, "opponentPace": 100.1},
        {"date": "2025-10-26", "statValue": 30, "opponentTeamId": "GSW", "opponentDefRating": 103.5, "opponentPace": 101.2},
    ]

    class DummyClient:
        @staticmethod
        def find_player_id_by_name(name):
            return None

        @staticmethod
        def find_player_id(name):
            return None

        @staticmethod
        def fetch_recent_games_by_name(name, limit=8):
            return sample_recent[:limit]

    monkeypatch.setattr(main_mod, 'nba_stats_client', DummyClient)

    client = TestClient(app)
    resp = client.get('/api/player_context?player=Test+Player&limit=3')
    assert resp.status_code == 200
    data = resp.json()
    assert data['player'] == 'Test Player'
    assert isinstance(data.get('recentGames'), list)
    assert len(data['recentGames']) == 3
    assert 'rollingAverages' in data
    assert isinstance(data['rollingAverages'], dict)
