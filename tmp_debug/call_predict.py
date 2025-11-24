import json
from urllib import request
url = 'http://127.0.0.1:8000/api/predict'
data = json.dumps({
    'player': 'Test Player',
    'stat': 'points',
    'line': 20.5,
    'player_data': {'seasonAvg': 22.0},
    'opponent_data': {}
}).encode('utf-8')
req = request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
try:
    with request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode('utf-8')
        print('status', resp.status)
        print(body)
except Exception as e:
    print('error', e)
