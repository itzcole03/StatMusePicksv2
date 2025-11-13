import json
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
                {"gameDate": "2025-11-01", "statValue": 30.0},
                {"gameDate": "2025-10-30", "statValue": 28.0},
            ],
            "seasonAvg": 29.0,
            "fetchedAt": "2025-11-11T00:00:00Z",
            "contextualFactors": {"homeAway": "home", "daysRest": 2}
        },
        "opponent_data": {"defensiveRating": 105, "pace": 99}
    }

    resp = client.post("/api/predict", json=payload)
    print("status_code:", resp.status_code)
    try:
        print(json.dumps(resp.json(), indent=2))
    except Exception:
        print(resp.text)


if __name__ == "__main__":
    main()
