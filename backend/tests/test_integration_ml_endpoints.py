import os
import joblib
import numpy as np
from pathlib import Path

from fastapi.testclient import TestClient
import importlib
import backend.main as backend_main


class DummyModel:
    """Module-level dummy model so joblib can pickle it from tests.

    Returns a fixed numeric prediction regardless of features.
    """

    def __init__(self, v: float = 1.0):
        self.v = float(v)

    def predict(self, X):
        import numpy as _np

        return _np.array([float(self.v)])


def test_models_load_and_predict(tmp_path):
    """Integration test: save a dummy model, load it via the API, and predict."""
    models_dir = tmp_path / "models_store"
    models_dir.mkdir()

    # persist a dummy model for "LeBron James"
    mdl = DummyModel(42.0)
    joblib.dump(mdl, models_dir / "LeBron_James.pkl")

    # Ensure the running app uses our temporary models dir by setting the
    # environment variable before importing/reloading the app module.
    os.environ["MODEL_STORE_DIR"] = str(models_dir)
    importlib.reload(backend_main)
    client = TestClient(backend_main.app)

    # Load the model through the endpoint (fastapi_nba expects a query param)
    resp = client.post("/api/models/load", params={"player": "LeBron James"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # Support both shapes: older main.py returned {'ok': True, 'loaded': ..}
    # while `fastapi_nba.py` returns {'player':.., 'loaded': ..}.
    assert (data.get("ok") is True) or (data.get("loaded") is True)

    # Ensure the running app's ml_service registry also knows about the model
    try:
        import backend.fastapi_nba as nba
        if getattr(nba, 'ml_service', None) and getattr(nba.ml_service, 'registry', None):
            # point the registry at our temp models dir and attempt to load
            try:
                nba.ml_service.registry.model_dir = Path(str(models_dir))
            except Exception:
                pass
            try:
                nba.ml_service.registry.load_model("LeBron James")
            except Exception:
                # best-effort; proceed even if it fails
                pass
    except Exception:
        pass

    # Now call predict and ensure the model output is used (not fallback)
    player_data = {"rollingAverages": {"last5Games": 25.0}, "seasonAvg": 20.0}
    resp2 = client.post(
        "/api/predict",
        json={"player": "LeBron James", "stat": "PTS", "line": 10.0, "player_data": player_data, "model_dir": str(models_dir)},
    )
    assert resp2.status_code == 200, resp2.text
    out2 = resp2.json()
    # Some routes wrap the prediction in {'ok': True, 'prediction': {...}}
    if out2.get("prediction") is not None:
        pred = out2.get("prediction")
    else:
        pred = out2

    assert pred is not None, f"missing prediction: {resp2.text}"
    assert pred.get("player") == "LeBron James"
    # DummyModel returns 42.0
    assert float(pred.get("predicted_value")) == 42.0


def test_predict_fallback_when_no_model(tmp_path):
    """Integration test: when no model exists, the service falls back to recent averages."""
    # Ensure the app is reloaded so it picks up any env changes and a clean
    # ml_service/registry state for the test. This mirrors how the app is
    # initialized in production and avoids relying on global state created
    # by other tests.
    importlib.reload(backend_main)
    client = TestClient(backend_main.app)

    player_data = {"rollingAverages": {"last5Games": 15.0}, "seasonAvg": 12.0}
    resp = client.post(
        "/api/predict",
        json={"player": "Random Player", "stat": "PTS", "line": 10.0, "player_data": player_data},
    )
    assert resp.status_code == 200, resp.text
    out = resp.json()
    # Accept either wrapped or direct response
    pred = out.get("prediction") or out
    assert pred is not None, f"missing prediction: {resp.text}"
    # Fallback should use recent_avg (last5Games)
    assert float(pred.get("predicted_value")) == 15.0
    # probabilities should be within [0,1]
    assert 0.0 <= float(pred.get("over_probability")) <= 1.0
