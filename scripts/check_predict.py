import json
import sys
import urllib.request

url = "http://localhost:8000/api/predict"
payload = {
    "player": "LeBron James",
    "stat": "points",
    "line": 25.5,
    "player_data": {},
    "opponent_data": {},
}

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    url, data=data, headers={"Content-Type": "application/json"}
)
try:
    resp = urllib.request.urlopen(req, timeout=10)
    body = resp.read().decode("utf-8")
    print(body)
except Exception as e:
    print("ERROR:", str(e))
    sys.exit(1)
