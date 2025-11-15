import numpy as np

from backend.services.calibration_service import (
    CalibratorRegistry,
    fit_isotonic_and_register,
    apply_calibrator,
    brier_score,
)


def test_isotonic_calibration_improves_brier(tmp_path):
    rng = np.random.RandomState(42)
    n = 1000
    # raw predictor that is miscalibrated: raw in [0,1]
    raw = rng.beta(2, 5, size=n)
    # true underlying probability is an affine transform of raw (so raw is not perfectly calibrated)
    true_prob = 0.2 + 0.6 * raw
    true_prob = np.clip(true_prob, 0.0, 1.0)
    # sample binary outcomes
    y = rng.binomial(1, true_prob, size=n)

    # baseline Brier score using raw predictions
    brier_before = brier_score(y, raw)

    # split train/val
    train_n = int(n * 0.7)
    raw_train, y_train = raw[:train_n], y[:train_n]
    raw_val, y_val = raw[train_n:], y[train_n:]

    # use a temp CalibratorRegistry rooted at tmp_path
    registry = CalibratorRegistry(base_path=tmp_path)

    # fit and register
    meta = fit_isotonic_and_register("test_model", raw_train, y_train, registry=registry, metadata={"note": "unit test"})

    # apply to validation set
    calibrated = apply_calibrator("test_model", raw_val, registry=registry, version_id=meta.version_id)

    brier_after = brier_score(y_val, calibrated)

    # calibration should not make things worse; expect improvement
    assert brier_after <= brier_before

    # also ensure registry can load latest
    loaded = registry.load_calibrator("test_model", version_id=meta.version_id)
    assert loaded is not None
    pred_again = loaded.predict(raw_val)
    assert np.allclose(pred_again, calibrated)
