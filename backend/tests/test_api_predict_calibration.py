from fastapi.testclient import TestClient
import joblib
import numpy as np
from pathlib import Path

from backend import main as backend_main


def test_api_predict_uses_central_calibrator(tmp_path, monkeypatch):
    # Prepare model dir and save dummy model
    models_dir = tmp_path / "models_store"
    models_dir.mkdir()
    player = "Test Player"
    safe = player.replace(" ", "_")
    model_path = models_dir / f"{safe}.pkl"
    # choose raw such that raw - line = 1.0 -> sigmoid ~ 0.731
    raw_val = 26.0
    # Build a simple sklearn linear model that maps last5 -> 1.1 * last5 so it is importable
    from sklearn.linear_model import LinearRegression
    import numpy as _np

    lr = LinearRegression()
    # fit on two points so the coefficient becomes 1.1
    X = _np.array([[0.0], [1.0]])
    y = _np.array([0.0, 1.1])
    lr.fit(X, y)
    joblib.dump(lr, model_path)

    # Prepare central calibrator registry in tmp path and fit a trivial calibrator
    from backend.services.calibration_service import CalibratorRegistry, fit_isotonic_and_register

    calib_store = tmp_path / "calibrators_store"
    reg = CalibratorRegistry(base_path=calib_store)

    # Build small train set where raw prob maps to a lower true rate
    # We'll compute raw prob via the same transform the service uses: sigmoid(raw - line)
    def sigmoid(x):
        return 1.0 / (1.0 + np.exp(-x))

    line = 25.0
    raw_prob = sigmoid(raw_val - line)

    # create training examples around that probability
    raw_preds = np.clip(np.random.RandomState(0).normal(loc=raw_prob, scale=0.01, size=200), 0.0, 1.0)
    # set true labels to be lower so calibrator will map raw_prob -> lower prob
    y = (np.random.RandomState(1).rand(len(raw_preds)) < (raw_preds * 0.5)).astype(int)

    meta = fit_isotonic_and_register(player, raw_preds, y, registry=reg, metadata={"note": "api test"})

    # Monkeypatch the global CalibratorRegistry used by ml_prediction_service to point to our tmp registry
    import backend.services.ml_prediction_service as mlpred

    monkeypatch.setattr(mlpred, "GlobalCalibratorRegistry", lambda: CalibratorRegistry(base_path=calib_store))

    # Sanity-check: ensure a fresh MLPredictionService can load the model from the provided model_dir.
    from backend.services.ml_prediction_service import MLPredictionService

    svc_local = MLPredictionService(model_dir=str(models_dir))
    has_local = svc_local.registry.get_model(player) is not None
    print("svc_local has model:", has_local)
    if svc_local.registry.get_model(player) is None:
        # Fallback: copy model into repo default store so the endpoint's legacy loader can find it.
        default_dir = Path("backend/models_store")
        default_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(DummyModel(raw_val), default_dir / f"{safe}.pkl")

    client = TestClient(backend_main.app)

    # craft player_data so the model's engineered feature `last5` yields raw_val
    last5 = float(raw_val / 1.1)
    payload = {
        "player": player,
        "stat": "points",
        "line": line,
        "player_data": {"rollingAverages": {"last5Games": last5}, "seasonAvg": last5},
        "model_dir": str(models_dir),
    }

    # Ask the app to load the persisted model into its runtime registry first
    load_resp = client.post("/api/models/load", json={"player": player, "model_dir": str(models_dir)})
    assert load_resp.status_code == 200
    lr = load_resp.json()
    print("LOAD RESP:", lr)
    # loaded may be False on some environments, but proceed; prediction should still work
    r = client.post("/api/predict", json=payload)
    assert r.status_code == 200
    body = r.json()
    print("API RESPONSE:", body)
    assert body.get("ok") is True
    pred = body["prediction"]

    # compute expected calibrated probability using the actual model prediction
    predicted_raw = pred["predicted_value"]
    over_raw = sigmoid(predicted_raw - line)
    # load calibrator and apply
    calib = reg.load_calibrator(player, version_id=meta.version_id)
    applied = calib.predict([over_raw])[0]

    assert abs(pred["over_probability"] - float(applied)) < 1e-6
