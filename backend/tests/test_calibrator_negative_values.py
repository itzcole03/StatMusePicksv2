import asyncio
import math

import pytest

from backend.services.ml_prediction_service import MLPredictionService


def run_async(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


class NanCal:
    def __call__(self, p):
        return float('nan')


class InfCal:
    def __call__(self, p):
        return float('inf')


class BigCal:
    def __call__(self, p):
        return 1e40


class NegCal:
    def __call__(self, p):
        return -10.0


def test_calibrator_returns_nan(tmp_path):
    svc = MLPredictionService(model_dir=str(tmp_path))
    svc.registry.save_calibrator("NaN Player", NanCal())
    out = run_async(svc._apply_calibration(0.6, player_name="NaN Player"))
    # NaN should be treated as invalid and fall back to scalar (unchanged)
    assert abs(out - 0.6) < 1e-9


def test_calibrator_returns_infinite(tmp_path):
    svc = MLPredictionService(model_dir=str(tmp_path))
    svc.registry.save_calibrator("Inf Player", InfCal())
    out = run_async(svc._apply_calibration(0.6, player_name="Inf Player"))
    # Infinity is invalid -> fallback to scalar
    assert abs(out - 0.6) < 1e-9


def test_calibrator_returns_very_large_number(tmp_path):
    svc = MLPredictionService(model_dir=str(tmp_path))
    svc.registry.save_calibrator("Big Player", BigCal())
    out = run_async(svc._apply_calibration(0.6, player_name="Big Player"))
    # Very large values should be clamped to 1.0
    assert out == 1.0


def test_calibrator_returns_negative_out_of_range(tmp_path):
    svc = MLPredictionService(model_dir=str(tmp_path))
    svc.registry.save_calibrator("Neg Player", NegCal())
    out = run_async(svc._apply_calibration(0.6, player_name="Neg Player"))
    # Negative values should be clamped to 0.0
    assert out == 0.0
