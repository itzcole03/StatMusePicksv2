from fastapi.testclient import TestClient
import json

from backend import fastapi_nba


client = TestClient(fastapi_nba.app)


class DummyCache:
    def __init__(self, payload):
        self._payload = payload

    def get(self, key):
        # return bytes to emulate redis-python behavior
        return json.dumps(self._payload).encode('utf-8')

    def setex(self, key, ttl, value):
        # noop for test
        self._last = (key, ttl, value)


def test_predict_uses_redis_cache(monkeypatch):
    # prepare a cached prediction
    cached = {
        'player': 'LeBron James',
        'stat': 'points',
        'line': 25.5,
        'predicted_value': 27.3,
        'over_probability': 0.68,
        'under_probability': 0.32,
        'recommendation': 'OVER',
        'expected_value': 0.18,
        'confidence': 68.0
    }

    monkeypatch.setattr(fastapi_nba, 'redis_client', DummyCache(cached))

    payload = {
        'player': 'LeBron James',
        'stat': 'points',
        'line': 25.5,
        'player_data': {},
        'opponent_data': {}
    }

    r = client.post('/api/predict', json=payload)
    assert r.status_code == 200
    data = r.json()
    # Response should match cached payload (FastAPI will coerce types)
    assert data.get('player') == 'LeBron James'
    assert data.get('predicted_value') == 27.3
    assert abs(data.get('over_probability') - 0.68) < 1e-6
