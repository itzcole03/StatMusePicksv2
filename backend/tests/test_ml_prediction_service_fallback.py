import asyncio
from backend.services.ml_prediction_service import MLPredictionService


def test_ml_prediction_fallback_no_model(tmp_path):
    # Create an empty temporary models directory to ensure no models exist
    model_dir = tmp_path / "models_store"
    model_dir.mkdir()

    svc = MLPredictionService(model_dir=str(model_dir))

    player_data = {
        "recentGames": [
            {"gameDate": "2025-11-01", "statValue": 18},
            {"gameDate": "2025-11-03", "statValue": 22},
            {"gameDate": "2025-11-05", "statValue": 20},
        ],
        "seasonAvg": 20,
        "contextualFactors": {"homeAway": "away", "daysRest": 1},
    }

    opponent_data = {"defensiveRating": 110, "pace": 98}

    result = asyncio.run(svc.predict("Test Player", "points", 21.5, player_data, opponent_data))

    assert isinstance(result, dict)
    # Fallback must provide these keys
    assert "over_probability" in result
    assert "predicted_value" in result
    # Probabilities should be within [0,1]
    assert 0.0 <= float(result["over_probability"]) <= 1.0
    # Confidence present and numeric
    assert "confidence" in result