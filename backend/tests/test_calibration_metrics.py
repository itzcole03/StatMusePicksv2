import numpy as np

from backend.evaluation.calibration_metrics import expected_calibration_error, brier_score
from backend.services.calibration_service import fit_isotonic_and_register, CalibratorRegistry, apply_calibrator


def test_ece_and_brier_improve_after_calibration(tmp_path):
    rng = np.random.RandomState(0)
    n = 2000
    # construct miscalibrated predictions
    raw = rng.beta(2.0, 6.0, size=n)
    true_prob = 0.15 + 0.7 * raw
    true_prob = np.clip(true_prob, 0.0, 1.0)
    y = rng.binomial(1, true_prob, size=n)

    # baseline metrics on held-out portion
    split = int(0.7 * n)
    raw_train, y_train = raw[:split], y[:split]
    raw_val, y_val = raw[split:], y[split:]

    ece_before = expected_calibration_error(y_val, raw_val, n_bins=10)
    brier_before = brier_score(y_val, raw_val)

    # fit calibrator on train
    registry = CalibratorRegistry(base_path=tmp_path)
    meta = fit_isotonic_and_register("metric_test", raw_train, y_train, registry=registry, metadata={"note": "unit"})
    calibrated = apply_calibrator("metric_test", raw_val, registry=registry, version_id=meta.version_id)

    ece_after = expected_calibration_error(y_val, calibrated, n_bins=10)
    brier_after = brier_score(y_val, calibrated)

    # Expect calibration to improve (or at least not significantly worsen) metrics.
    # ECE should not increase.
    assert ece_after <= ece_before + 1e-8
    # Brier score may occasionally slightly increase due to sample noise; allow small tolerance (1%).
    assert brier_after <= brier_before * 1.01 + 1e-12
