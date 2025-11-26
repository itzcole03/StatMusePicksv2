import json
import os
import time

import requests

# Wait briefly if server is just starting
time.sleep(1)

url = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000/api/predict")
payload = {
    "player": "LeBron James",
    "stat": "points",
    "line": 25.5,
    "player_data": {
        "recentGames": [
            {"gameDate": "2025-11-01", "statValue": 28},
            {"gameDate": "2025-11-03", "statValue": 30},
            {"gameDate": "2025-11-05", "statValue": 26},
        ],
        "seasonAvg": 27.5,
        "rollingAverages": {"last5Games": 28},
    },
    "opponent_data": {"defensiveRating": 105, "pace": 99},
}

print("POST", url)
resp = requests.post(url, json=payload, timeout=10)
print("Status:", resp.status_code)
try:
    print(json.dumps(resp.json(), indent=2))
except Exception:
    print(resp.text)
