from fastapi.testclient import TestClient
import asyncio

from backend import fastapi_nba

client = TestClient(fastapi_nba.app)


def test_batch_predict_timeout(monkeypatch):
    # make ml_service.predict sleep longer than timeout
    class SlowService:
        async def predict(self, player_name, stat_type, line, player_data, opponent_data):
            await asyncio.sleep(2)
            return {'player': player_name, 'stat': stat_type, 'line': line, 'predicted_value': 10.0, 'over_probability': 0.6, 'under_probability': 0.4, 'recommendation': 'OVER', 'expected_value': 0.1, 'confidence': 60.0}

    monkeypatch.setattr(fastapi_nba, 'ml_service', SlowService())

    payload = [
        {'player': 'A', 'stat': 'points', 'line': 5.0},
        {'player': 'B', 'stat': 'points', 'line': 10.0}
    ]

    # set timeout_seconds to 1 to force timeout
    r = client.post('/api/batch_predict?timeout_seconds=1', json=payload)
    assert r.status_code == 200
    data = r.json()
    assert 'predictions' in data
    # both entries should have an error due to timeout
    for p in data['predictions']:
        assert p.get('error') in ('prediction timeout',)
