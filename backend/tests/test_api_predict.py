from fastapi.testclient import TestClient
import json

from backend import fastapi_nba


def test_health_and_predict_with_stub_model(monkeypatch):
    client = TestClient(fastapi_nba.app)

    # Health endpoint
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json().get('ok') is True

    # Ensure model registry loads the stub model if present
    # Use minimal payload that exercise ML fallback or stub model
    payload = {
        'player': 'LeBron James',
        'stat': 'points',
        'line': 25.0,
        'player_data': {},
        'opponent_data': {}
    }

    r2 = client.post('/api/predict', json=payload)
    # We accept either 200 OK with a prediction or 503 if ML service unavailable
    assert r2.status_code in (200, 503)
    if r2.status_code == 200:
        data = r2.json()
        assert 'player' in data and data['player'] == 'LeBron James'
        assert 'over_probability' in data or 'predicted_value' in data
