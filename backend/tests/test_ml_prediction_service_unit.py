import asyncio

from backend.services.ml_prediction_service import MLPredictionService


def test_ml_prediction_with_persisted_model():
    svc = MLPredictionService(model_dir="./backend/models_store")

    player_data = {
        "recentGames": [
            {"gameDate": "2025-11-01", "statValue": 28},
            {"gameDate": "2025-11-03", "statValue": 30},
            {"gameDate": "2025-11-05", "statValue": 26},
        ],
        "seasonAvg": 27.5,
        "contextualFactors": {"homeAway": "home", "daysRest": 2},
    }

    opponent_data = {"defensiveRating": 105, "pace": 99}

    result = asyncio.run(svc.predict("LeBron James", "points", 25.5, player_data, opponent_data))

    assert isinstance(result, dict)
    assert "over_probability" in result
    assert 0.0 <= float(result["over_probability"]) <= 1.0
    assert "predicted_value" in result
