import asyncio


def test_ml_prediction_fallback():
    from backend.services.ml_prediction_service import MLPredictionService

    svc = MLPredictionService()

    player_data = {
        "recentGames": [
            {"date": "2025-01-01", "statValue": 22},
            {"date": "2025-01-02", "statValue": 24},
            {"date": "2025-01-03", "statValue": 26},
        ],
        "seasonAvg": 24.0,
        "contextualFactors": {"homeAway": "away", "daysRest": 1},
    }

    # Use asyncio.run to execute the async predict method
    result = asyncio.run(svc.predict("Test Player", "points", 23.5, player_data, {}))

    assert isinstance(result, dict)
    assert "over_probability" in result
    assert 0.0 <= result["over_probability"] <= 1.0
    assert "predicted_value" in result
