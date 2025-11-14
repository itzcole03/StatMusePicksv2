import os
import joblib
import shutil
from pathlib import Path
import numpy as np
from fastapi.testclient import TestClient

from backend.main import app
from backend.tests.dummy_model import DummyModel

MODELS_DIR = Path("backend/models_store")


def setup_module(module):
    # ensure a clean models_store
    if MODELS_DIR.exists():
        shutil.rmtree(MODELS_DIR)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    # dump a dummy model for `John Doe`
    joblib.dump(DummyModel(), MODELS_DIR / "John_Doe.pkl")


def teardown_module(module):
    # clean up artifacts
    try:
        if MODELS_DIR.exists():
            shutil.rmtree(MODELS_DIR)
    except Exception:
        pass


def test_load_model_and_predict():
    client = TestClient(app)

    # load the model via API
    rv = client.post("/api/models/load", json={"player": "John Doe", "model_dir": str(MODELS_DIR)})
    assert rv.status_code == 200
    data = rv.json()
    assert data.get("ok") is True
    assert data.get("loaded") is True
    assert data.get("versions", 0) >= 1

    # craft player_data with rollingAverages that the model uses
    player_data = {
        "rollingAverages": {"last5Games": 20.0, "last3Games": 18.0},
        "seasonAvg": 15.0,
        "contextualFactors": {},
    }

    rv2 = client.post(
        "/api/predict",
        json={"player": "John Doe", "stat": "PTS", "line": 10.0, "player_data": player_data, "model_dir": str(MODELS_DIR)},
    )
    assert rv2.status_code == 200
    out = rv2.json()
    assert out.get("ok") is True
    pred = out.get("prediction")
    assert pred is not None
    # our DummyModel returns last5 * 1.1 -> 22.0
    assert float(pred.get("predicted_value")) == 22.0
    assert pred.get("recommendation") == "OVER"
    assert pred.get("player") == "John Doe"
    assert pred.get("stat") == "PTS"
