import json
import traceback

from fastapi.testclient import TestClient

from backend.main import app


def main():
    client = TestClient(app)

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

    try:
        resp = client.post("/api/predict", json=payload)
        print("Status:", resp.status_code)
        try:
            print(json.dumps(resp.json(), indent=2))
        except Exception:
            print(resp.text)
    except Exception as e:
        print("Request raised exception:")
        traceback.print_exc()


if __name__ == "__main__":
    main()
