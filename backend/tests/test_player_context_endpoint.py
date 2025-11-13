from fastapi.testclient import TestClient
from backend.main import app
import backend.main as main_mod


def test_player_context_endpoint_monkeypatched(monkeypatch):
    # Provide deterministic recent games via monkeypatching nba_stats_client
    sample_recent = [
        {"date": "2025-11-05", "statValue": 28, "opponentTeamId": "BOS", "opponentDefRating": 105.0},
        {"date": "2025-11-02", "statValue": 24, "opponentTeamId": "NYK", "opponentDefRating": 110.0},
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
            return sample_recent

    monkeypatch.setattr(main_mod, 'nba_stats_client', DummyClient)

    client = TestClient(app)
    resp = client.get('/api/player_context?player_name=LeBron+James&limit=2')
    assert resp.status_code == 200
    data = resp.json()
    assert data['player'] == 'LeBron James'
    assert 'recentGames' in data and len(data['recentGames']) == 2
    # rollingAverages should be present and include last_3 or similar keys
    assert 'rollingAverages' in data
    assert isinstance(data['rollingAverages'], dict)
    # contextualFactors should be present
    assert 'contextualFactors' in data
