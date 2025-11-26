import os

# Ensure repo import paths resolve when tests run in CI
import sys

import joblib
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.fastapi_nba import app


class DummyModel:
    def predict(self, X):
        # Return a fixed prediction irrespective of input
        return [42.0]


def test_api_predict_with_persisted_model(tmp_path):
    # Arrange: create a dummy model and write it to the real model store
    model_dir = os.path.join(os.path.dirname(__file__), "..", "models_store")
    model_dir = os.path.abspath(model_dir)
    os.makedirs(model_dir, exist_ok=True)

    player_name = "LeBron James"
    safe = player_name.replace(" ", "_")
    model_path = os.path.join(model_dir, f"{safe}.pkl")

    # Persist dummy model (top-level class is picklable)
    joblib.dump(DummyModel(), model_path)

    try:
        # Act: start test client (will trigger startup preload)
        client = TestClient(app)

        payload = {
            "player": player_name,
            "stat": "points",
            "line": 25.5,
            "player_data": {
                "recentGames": [
                    {"gameDate": "2025-11-01", "statValue": 30.0, "raw": {}},
                    {"gameDate": "2025-10-30", "statValue": 28.0, "raw": {}},
                ],
                "seasonAvg": 29.0,
                "fetchedAt": "2025-11-11T00:00:00Z",
            },
            "opponent_data": {},
        }

        resp = client.post("/api/predict", json=payload)

        assert resp.status_code == 200, resp.text
        data = resp.json()

        # Assert: model was used and produced our DummyModel value
        assert data.get("player") == player_name
        assert float(data.get("predicted_value")) == 42.0
        assert "over_probability" in data
        assert "recommendation" in data

    finally:
        # Clean up the dummy model file
        try:
            os.remove(model_path)
        except Exception:
            pass
