import asyncio
import os
import joblib
from pathlib import Path

import pytest

from backend.services.ml_prediction_service import MLPredictionService


class CallableCalibrator:
    def __call__(self, p: float) -> float:
        # scale probability down by 0.8
        return float(p) * 0.8


class TransformCalibrator:
    def transform(self, arr):
        # expect iterable input, return scaled array
        return [float(arr[0]) * 0.5]


class PredictProbaCalibrator:
    def predict_proba(self, X):
        # X is expected to be [[prob]]; return [[1 - prob*0.5, prob*0.5]]
        prob = float(X[0][0])
        return [[1.0 - prob * 0.5, prob * 0.5]]


def run_async(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


def test_scalar_fallback_no_calibrator():
    svc = MLPredictionService(model_dir=str(Path("backend/models_store")))
    # default calibration_scale == 1.0, so value should be unchanged
    out = run_async(svc._apply_calibration(0.6, player_name="NoOne"))
    assert pytest.approx(out, rel=1e-6) == 0.6


def test_callable_calibrator_in_memory(tmp_path):
    svc = MLPredictionService(model_dir=str(tmp_path))
    cal = CallableCalibrator()
    svc.registry.save_calibrator("John Doe", cal)
    out = run_async(svc._apply_calibration(0.6, player_name="John Doe"))
    assert pytest.approx(out, rel=1e-6) == 0.48


def test_transform_calibrator_in_memory(tmp_path):
    svc = MLPredictionService(model_dir=str(tmp_path))
    cal = TransformCalibrator()
    svc.registry.save_calibrator("Jane Roe", cal)
    out = run_async(svc._apply_calibration(0.6, player_name="Jane Roe"))
    # transform returns [prob * 0.5]
    assert pytest.approx(out, rel=1e-6) == 0.3


def test_predict_proba_calibrator_via_persistence(tmp_path):
    # persist a calibrator and load it back in a fresh service instance
    svc = MLPredictionService(model_dir=str(tmp_path))
    cal = PredictProbaCalibrator()
    svc.registry.save_calibrator("Sam Player", cal)

    # create a new service pointing to the same dir and ensure it loads the persisted calibrator
    svc2 = MLPredictionService(model_dir=str(tmp_path))
    loaded = svc2.registry.load_calibrator("Sam Player")
    assert loaded is not None
    out = run_async(svc2._apply_calibration(0.8, player_name="Sam Player"))
    # predict_proba returns [[1 - prob*0.5, prob*0.5]] -> returns prob*0.5
    assert pytest.approx(out, rel=1e-6) == 0.4
