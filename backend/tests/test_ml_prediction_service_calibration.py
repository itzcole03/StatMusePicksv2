import asyncio
from pathlib import Path

import joblib
import numpy as np

from backend.services.calibration_service import CalibratorRegistry, fit_isotonic_and_register
import backend.services.ml_prediction_service as mlpred
from backend.services.ml_prediction_service import MLPredictionService


class DummyModel:
    def __init__(self, raw):
        self.raw = raw

    def predict(self, X):
        return np.array([self.raw])


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def test_ml_prediction_service_applies_central_calibrator(tmp_path, monkeypatch):
    # Prepare model dir and save a deterministic dummy model
    models_dir = tmp_path / "models_store"
    models_dir.mkdir()
    player = "Unit Player"
    safe = player.replace(" ", "_")
    model_path = models_dir / f"{safe}.pkl"

    # raw value the DummyModel will produce
    raw_val = 26.0
    dm = DummyModel(raw_val)
    joblib.dump(dm, model_path)

    # Prepare central calibrator registry and fit a trivial isotonic calibrator
    calib_store = tmp_path / "calibrators_store"
    reg = CalibratorRegistry(base_path=calib_store)

    line = 25.0
    raw_prob = sigmoid(raw_val - line)

    # training examples around that probability; true labels biased lower
    rng = np.random.RandomState(0)
    raw_preds = np.clip(rng.normal(loc=raw_prob, scale=0.01, size=200), 0.0, 1.0)
    y = (rng.rand(len(raw_preds)) < (raw_preds * 0.4)).astype(int)

    meta = fit_isotonic_and_register(player, raw_preds, y, registry=reg, metadata={"note": "unit test"})

    # Monkeypatch the global registry used by ml_prediction_service
    monkeypatch.setattr(mlpred, "GlobalCalibratorRegistry", lambda: CalibratorRegistry(base_path=calib_store))

    svc = MLPredictionService(model_dir=str(models_dir))

    # call the async predict method
    player_data = {"rollingAverages": {"last5Games": raw_val}, "seasonAvg": raw_val}
    loop = asyncio.get_event_loop()
    res = loop.run_until_complete(svc.predict(player, "points", line, player_data))

    assert res.get("ok", True) is True

    # compute expected calibrated probability based on actual predicted_value
    predicted_raw = res["predicted_value"]
    over_raw = sigmoid(predicted_raw - line)
    calib = reg.load_calibrator(player, version_id=meta.version_id)
    expected = float(calib.predict([over_raw])[0])

    assert abs(res["over_probability"] - expected) < 1e-6
