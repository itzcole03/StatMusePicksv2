import numpy as np

from backend.evaluation.calibration_metrics import (
    brier_score,
    expected_calibration_error,
)


def test_brier_and_ece_perfect():
    y_true = np.array([0, 1, 1, 0, 1])
    y_prob = np.array([0.0, 1.0, 1.0, 0.0, 1.0])
    assert brier_score(y_true, y_prob) == 0.0
    assert expected_calibration_error(y_true, y_prob) == 0.0


def test_brier_random():
    rng = np.random.RandomState(0)
    y_true = rng.randint(0, 2, size=100)
    y_prob = rng.rand(100)
    bs = brier_score(y_true, y_prob)
    assert 0.0 <= bs <= 1.0
    ece = expected_calibration_error(y_true, y_prob, n_bins=5)
    assert 0.0 <= ece <= 1.0
