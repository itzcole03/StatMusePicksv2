import numpy as np
from backend.evaluation import calibration as calib


def test_fit_isotonic_basic_monotonic():
    p = np.array([0.1, 0.2, 0.3, 0.6, 0.8])
    y = np.array([0.0, 0.0, 1.0, 1.0, 1.0])
    xs, ys = calib.fit_isotonic(p, y)
    assert xs.shape[0] == ys.shape[0]
    # ys must be non-decreasing
    assert np.all(np.diff(ys) >= -1e-12)


def test_fit_isotonic_non_monotonic():
    p = np.array([0.1, 0.4, 0.3, 0.9, 0.2])
    y = np.array([0.0, 1.0, 0.0, 1.0, 0.0])
    xs, ys = calib.fit_isotonic(p, y)
    assert xs.shape[0] == ys.shape[0]
    assert np.all(np.diff(ys) >= -1e-12)
    # applying should produce values between 0 and 1
    preds = calib.apply_isotonic(p, xs, ys)
    assert np.all(preds >= 0.0) and np.all(preds <= 1.0)


def test_fit_isotonic_empty():
    xs, ys = calib.fit_isotonic(np.array([]), np.array([]))
    assert xs.size == 0 and ys.size == 0


def test_kfold_and_ensemble_consistency():
    rng = np.random.default_rng(0)
    n = 60
    p = rng.random(n)
    # synthetic outcome with some calibration distortion
    y = (p + 0.1 * rng.normal(size=n) > 0.5).astype(float)

    models = calib.fit_isotonic_kfold(p, y, k=5, random_seed=0)
    assert isinstance(models, list) and len(models) >= 1
    ensemble = calib.apply_isotonic_ensemble(p, models)
    assert ensemble.shape[0] == n
    assert np.all(ensemble >= 0.0) and np.all(ensemble <= 1.0)
