import asyncio
import math

import pytest

from backend.services.ml_prediction_service import MLPredictionService


def run_async(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


class ReturnsNan:
    def __call__(self, p):
        return float('nan')


class ReturnsInf:
    def __call__(self, p):
        return float('inf')


class ReturnsTwo:
    def __call__(self, p):
        return 2.0


class ReturnsNeg:
    def __call__(self, p):
        return -0.5


def test_nan_fallback_to_scalar(tmp_path):
    svc = MLPredictionService(model_dir=str(tmp_path))
    svc.registry.save_calibrator('P1', ReturnsNan())
    out = run_async(svc._apply_calibration(0.6, player_name='P1'))
    # NaN should fall back to scalar (scale=1.0) -> unchanged
    assert math.isnan(out) is False
    assert abs(out - 0.6) < 1e-9


def test_inf_fallback_to_scalar(tmp_path):
    svc = MLPredictionService(model_dir=str(tmp_path))
    svc.registry.save_calibrator('P2', ReturnsInf())
    out = run_async(svc._apply_calibration(0.7, player_name='P2'))
    assert abs(out - 0.7) < 1e-9


def test_clamp_above_one(tmp_path):
    svc = MLPredictionService(model_dir=str(tmp_path))
    svc.registry.save_calibrator('P3', ReturnsTwo())
    out = run_async(svc._apply_calibration(0.5, player_name='P3'))
    # 2.0 should be clamped to 1.0
    assert out == 1.0


def test_clamp_negative_to_zero(tmp_path):
    svc = MLPredictionService(model_dir=str(tmp_path))
    svc.registry.save_calibrator('P4', ReturnsNeg())
    out = run_async(svc._apply_calibration(0.4, player_name='P4'))
    # negative values clamp to 0.0
    assert out == 0.0
