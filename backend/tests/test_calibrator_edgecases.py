import asyncio
from pathlib import Path

import pytest

from backend.services.ml_prediction_service import MLPredictionService


def run_async(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


def test_malformed_calibrator_fallback(tmp_path):
    svc = MLPredictionService(model_dir=str(tmp_path))

    class Malformed:
        # no callable/transform/predict_proba
        foo = 1

    svc.registry.save_calibrator("Malformed Player", Malformed())
    out = run_async(svc._apply_calibration(0.7, player_name="Malformed Player"))
    assert pytest.approx(out, rel=1e-6) == 0.7


def test_calibrator_raises_exception(tmp_path):
    svc = MLPredictionService(model_dir=str(tmp_path))

    class Raising:
        def __call__(self, p):
            raise RuntimeError("boom")

    svc.registry.save_calibrator("Raise Player", Raising())
    out = run_async(svc._apply_calibration(0.6, player_name="Raise Player"))
    # should fallback to scalar (default scale=1.0) -> unchanged
    assert pytest.approx(out, rel=1e-6) == 0.6


def test_calibrator_returns_non_float(tmp_path):
    svc = MLPredictionService(model_dir=str(tmp_path))

    class ReturnsList:
        def __call__(self, p):
            return ["0.8"]

    svc.registry.save_calibrator("List Player", ReturnsList())
    out = run_async(svc._apply_calibration(0.6, player_name="List Player"))
    # list -> cannot be coerced to float safely in our code path -> fallback
    assert pytest.approx(out, rel=1e-6) == 0.6


def test_transform_returns_bad_shape(tmp_path):
    svc = MLPredictionService(model_dir=str(tmp_path))

    class BadTransform:
        def transform(self, arr):
            return {"not": "a list"}

    svc.registry.save_calibrator("Transform Player", BadTransform())
    out = run_async(svc._apply_calibration(0.4, player_name="Transform Player"))
    assert pytest.approx(out, rel=1e-6) == 0.4


def test_scalar_scale_applied_when_no_per_player():
    svc = MLPredictionService()
    svc.set_calibration_scale(0.5)
    # prob = 0.8 -> 0.5 + (0.8 - 0.5) * 0.5 = 0.65
    out = run_async(svc._apply_calibration(0.8, player_name="NoCalib"))
    assert pytest.approx(out, rel=1e-6) == 0.65
