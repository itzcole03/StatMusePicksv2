from fastapi.testclient import TestClient
from backend.main import app
import backend.main as main_mod


def test_player_context_returns_cached(monkeypatch):
    cached_payload = {
        "player": "LeBron James",
        "player_id": None,
        "recentGames": [],
        "seasonAvg": 27.5,
        "fetchedAt": 1234567890,
        "cached": True,
    }

    async def fake_redis_get(key):
        return cached_payload

    # Replace redis_get_json used by the endpoint
    monkeypatch.setattr(main_mod, 'redis_get_json', fake_redis_get)

    client = TestClient(app)
    resp = client.get('/api/player_context?player_name=LeBron%20James&limit=3')
    assert resp.status_code == 200
    data = resp.json()
    assert data['cached'] is True
    assert data['player'] == 'LeBron James'
