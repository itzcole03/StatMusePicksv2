import asyncio

from backend.services.ml_prediction_service import MLPredictionService


def test_fallback_prediction_uses_last5():
    svc = MLPredictionService()
    player_data = {
        "rollingAverages": {"last5Games": 30.0},
        "seasonAvg": 28.0,
    }

    # Run the async predict synchronously for test
    res = asyncio.get_event_loop().run_until_complete(
        svc.predict("Anyone", "points", 27.5, player_data)
    )

    assert "over_probability" in res
    assert "recommendation" in res
    # last5=30, line=27.5 -> heuristic favors OVER (over_prob > 0.5)
    assert res["predicted_value"] == 30.0
    assert res["over_probability"] > 0.5
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
