import numpy as np

from backend.services.calibration_service import Calibrator
from backend.evaluation.calibration_metrics import expected_calibration_error, brier_score


def test_calibrator_improves_brier_and_ece():
    # Deterministic toy dataset: two raw score levels mapping perfectly to labels
    raw = np.array([0.2, 0.2, 0.8, 0.8])
    y = np.array([0, 0, 1, 1])

    # Raw metrics
    brier_raw = brier_score(y, raw)
    ece_raw = expected_calibration_error(y, raw, n_bins=2)

    # Fit isotonic calibrator deterministically
    calib = Calibrator()
    calib.fit(raw, y)
    calibrated = calib.predict(raw)

    brier_cal = brier_score(y, calibrated)
    ece_cal = expected_calibration_error(y, calibrated, n_bins=2)

    # Calibrated metrics should be strictly better in this toy example
    assert brier_cal < brier_raw, f"Expected calibrated Brier < raw Brier ({brier_cal} < {brier_raw})"
    assert ece_cal < ece_raw, f"Expected calibrated ECE < raw ECE ({ece_cal} < {ece_raw})"
