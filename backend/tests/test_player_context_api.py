from fastapi.testclient import TestClient
import time

from backend import main as backend_main


def sample_recent_games():
    return [
        {"date": "2025-11-01", "statValue": 20},
        {"date": "2025-11-03", "statValue": 25},
    ]


def test_player_context_endpoint(monkeypatch):
    client = TestClient(backend_main.app)

    # Patch nba_stats_client functions used by the endpoint
    import backend.services.nba_stats_client as nba_client

    monkeypatch.setattr(nba_client, 'find_player_id_by_name', lambda name: 123)
    # The main module may call fetch_recent_games_by_id or fetch_recent_games_by_name;
    # set both so the endpoint finds one.
    monkeypatch.setattr(nba_client, 'fetch_recent_games_by_id', lambda pid, limit=8: sample_recent_games(), raising=False)
    monkeypatch.setattr(nba_client, 'fetch_recent_games_by_name', lambda name, limit=8: sample_recent_games(), raising=False)

    resp = client.get('/api/player_context', params={'player_name': 'Test Player', 'limit': 2})
    assert resp.status_code == 200
    data = resp.json()
    # Pydantic response_model will coerce/validate fields; ensure expected values
    assert data['player'] == 'Test Player'
    assert data['player_id'] == 123
    assert isinstance(data.get('recentGames'), list)
    assert len(data['recentGames']) == 2
    assert isinstance(data.get('seasonAvg', None), (float, type(None)))
    assert isinstance(data.get('fetchedAt'), int)
    assert isinstance(data.get('cached'), bool)
