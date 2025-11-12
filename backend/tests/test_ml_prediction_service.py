import asyncio

from backend.services.ml_prediction_service import MLPredictionService


def test_feature_engineering_and_predict():
    svc = MLPredictionService()

    player_data = {
        "recentGames": [
            {"date": "2025-11-01", "statValue": 20},
            {"date": "2025-11-03", "statValue": 25},
            {"date": "2025-11-05", "statValue": 22},
        ],
        "seasonAvg": 22.0,
        "rollingAverages": {"last5Games": 22.3},
        "contextualFactors": {"homeAway": "home", "daysRest": 2, "isBackToBack": False},
    }

    # Run the async predict method using asyncio.run for modern event loop handling
    result = asyncio.run(svc.predict("Test Player", "points", 21.5, player_data, None))

    assert isinstance(result, dict)
    assert "over_probability" in result
    assert 0.0 <= result["over_probability"] <= 1.0
    assert result["predicted_value"] is not None
