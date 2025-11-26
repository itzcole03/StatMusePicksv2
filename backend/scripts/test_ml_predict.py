import asyncio
import json

from backend.services.ml_prediction_service import MLPredictionService


async def main():
    svc = MLPredictionService()
    player_data = {
        "recentGames": [
            {"gameDate": "2025-11-01", "statValue": 28},
            {"gameDate": "2025-11-03", "statValue": 30},
            {"gameDate": "2025-11-05", "statValue": 26},
        ],
        "seasonAvg": 27.5,
        "rollingAverages": {"last5Games": 28},
    }
    opponent_data = {"defensiveRating": 105, "pace": 99}

    res = await svc.predict("LeBron James", "points", 25.5, player_data, opponent_data)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
