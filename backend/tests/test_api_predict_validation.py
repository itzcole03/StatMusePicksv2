from fastapi.testclient import TestClient

from backend import fastapi_nba


client = TestClient(fastapi_nba.app)


def test_predict_rejects_negative_line():
    payload = {
        'player': 'LeBron James',
        'stat': 'points',
        'line': -5.0,
        'player_data': {},
        'opponent_data': {}
    }
    r = client.post('/api/predict', json=payload)
    assert r.status_code == 400
    assert 'line' in r.json().get('detail', '')


def test_predict_rejects_missing_player():
    payload = {
        'player': '',
        'stat': 'points',
        'line': 25.0,
    }
    r = client.post('/api/predict', json=payload)
    assert r.status_code == 400
    assert 'player' in r.json().get('detail', '')


def test_predict_accepts_valid_payload_or_service_unavailable():
    payload = {
        'player': 'LeBron James',
        'stat': 'points',
        'line': 25.0,
        'player_data': {},
        'opponent_data': {}
    }
    r = client.post('/api/predict', json=payload)
    assert r.status_code in (200, 503)
    # If 200, ensure top-level player key present
    if r.status_code == 200:
        data = r.json()
        assert data.get('player') == 'LeBron James' or (data.get('prediction') and data['prediction'].get('player') == 'LeBron James')
