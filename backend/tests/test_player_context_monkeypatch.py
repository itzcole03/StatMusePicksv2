from fastapi.testclient import TestClient
import backend.main as main_mod
from backend.main import app


def test_player_context_with_monkeypatched_nba_client(monkeypatch):
    # Deterministic sample recent games
    sample_recent = [
        {"date": "2025-11-05", "statValue": 22, "opponentTeamId": "BOS", "opponentDefRating": 105.0},
        {"date": "2025-11-03", "statValue": 26, "opponentTeamId": "NYK", "opponentDefRating": 110.0},
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

    # Monkeypatch the nba_stats_client used inside backend.main
    monkeypatch.setattr(main_mod, 'nba_stats_client', DummyClient)

    client = TestClient(app)
    resp = client.get('/api/player_context?player_name=Test+Player&limit=2')
    assert resp.status_code == 200
    data = resp.json()
    assert data['player'] == 'Test Player'
    assert isinstance(data.get('recentGames'), list)
    assert len(data['recentGames']) == 2
    assert 'rollingAverages' in data and isinstance(data['rollingAverages'], dict)
    assert 'contextualFactors' in data
