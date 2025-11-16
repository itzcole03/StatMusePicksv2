from fastapi.testclient import TestClient
import asyncio

from backend import fastapi_nba


client = TestClient(fastapi_nba.app)


def test_batch_predict_partial_success(monkeypatch):
    # Create a service that is fast for some players and slow for others
    class MixedService:
        async def predict(self, player_name, stat_type, line, player_data, opponent_data):
            # Fast for names ending with 'F', slow for names ending with 'S'
            if player_name.endswith('F'):
                await asyncio.sleep(0.01)
                return {'player': player_name, 'stat': stat_type, 'line': line, 'predicted_value': 10.0, 'over_probability': 0.6, 'under_probability': 0.4, 'recommendation': 'OVER', 'expected_value': 0.1, 'confidence': 60.0}
            else:
                await asyncio.sleep(2)
                return {'player': player_name, 'stat': stat_type, 'line': line, 'predicted_value': 9.0, 'over_probability': 0.4, 'under_probability': 0.6, 'recommendation': 'UNDER', 'expected_value': -0.1, 'confidence': 40.0}

    monkeypatch.setattr(fastapi_nba, 'ml_service', MixedService())

    payload = []
    for i in range(6):
        # alternate fast/slow
        suffix = 'F' if i % 2 == 0 else 'S'
        payload.append({'player': f'Player{i}{suffix}', 'stat': 'points', 'line': 10.0})

    # small overall timeout to force some slow ones to be cancelled
    r = client.post('/api/batch_predict?overall_timeout_seconds=1', json=payload)
    assert r.status_code == 200
    data = r.json()
    assert 'predictions' in data
    preds = data['predictions']
    # At least the fast ones should have predicted_value present; slow ones may have error
    fast_count = sum(1 for p in preds if p.get('player', '').endswith('F') and p.get('predicted_value') is not None)
    assert fast_count >= 2
