from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
resp = client.post('/api/predict', json={
    'player': 'Test Player',
    'stat': 'points',
    'line': 20.5,
    'player_data': {'seasonAvg': 22.0},
    'opponent_data': {}
})
print('status', resp.status_code)
print(resp.json())
