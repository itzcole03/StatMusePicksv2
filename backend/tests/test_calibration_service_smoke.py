import numpy as np
from backend.services.calibration_service import CalibrationService


def test_calibrator_improves_brier_and_ece(tmp_path):
    rng = np.random.RandomState(42)
    n = 2000
    # generate true probabilities from uniform, then binary outcomes
    true_p = rng.uniform(0.0, 1.0, size=n)
    y_true = rng.binomial(1, true_p, size=n)

    # create miscalibrated predictions by adding noise and a small bias
    y_pred = np.clip(true_p + rng.normal(scale=0.12, size=n) + 0.05, 0.0, 1.0)

    svc = CalibrationService()
    res = svc.fit_and_save("smoke_test_player", y_true, y_pred, method="isotonic")

    before = res.get("before", {})
    after = res.get("after", {})

    # Ensure we computed calibration metrics
    assert "brier" in before and "brier" in after
    assert "ece" in before and "ece" in after

    # Expect some improvement after isotonic calibration
    assert after["brier"] <= before["brier"]
    assert after["ece"] <= before["ece"]
