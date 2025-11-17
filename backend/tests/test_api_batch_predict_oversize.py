from fastapi.testclient import TestClient

from backend import fastapi_nba


client = TestClient(fastapi_nba.app)


def test_batch_predict_oversize():
    # Create a payload larger than default max_requests=50
    payload = [{'player': f'P{i}', 'stat': 'points', 'line': 10.0} for i in range(60)]
    r = client.post('/api/batch_predict', json=payload)
    assert r.status_code == 413
    data = r.json()
    assert 'detail' in data and 'exceeds max_requests' in data['detail']
