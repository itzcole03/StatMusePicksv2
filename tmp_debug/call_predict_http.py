import os
import requests

url = 'http://127.0.0.1:8000/api/predict'
body = {
    'player': 'Test Player',
    'stat': 'points',
    'line': 20.5,
    'player_data': {'seasonAvg': 22.0},
    'opponent_data': {}
}
resp = requests.post(url, json=body, timeout=10)
print('status', resp.status_code)
print(resp.text)
