from fastapi.testclient import TestClient
import asyncio

from backend import fastapi_nba


client = TestClient(fastapi_nba.app)


def test_batch_predict_overall_timeout(monkeypatch):
    # Make ml_service.predict sleep long so overall timeout triggers
    class SlowService:
        async def predict(self, player_name, stat_type, line, player_data, opponent_data):
            await asyncio.sleep(2)
            return {'player': player_name, 'stat': stat_type, 'line': line, 'predicted_value': 10.0, 'over_probability': 0.6, 'under_probability': 0.4, 'recommendation': 'OVER', 'expected_value': 0.1, 'confidence': 60.0}

    monkeypatch.setattr(fastapi_nba, 'ml_service', SlowService())

    payload = [
        {'player': f'A{i}', 'stat': 'points', 'line': 5.0} for i in range(5)
    ]

    # Set overall_timeout_seconds=1 to force batch-level timeout (per-call default timeout is higher)
    r = client.post('/api/batch_predict?overall_timeout_seconds=1', json=payload)
    assert r.status_code == 200
    data = r.json()
    assert 'predictions' in data
    # After overall timeout, each entry should have an error indicating batch timeout
    for p in data['predictions']:
        assert p.get('error') in ('batch timeout', 'prediction timeout') or p.get('predicted_value') is None
