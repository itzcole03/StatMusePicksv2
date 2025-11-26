import sys
from pathlib import Path

import numpy as np

ROOT = Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_fit_calibrator_requires_minimum_rows(tmp_path):
    from backend.services.calibration_service import CalibrationService

    calib_srv = CalibrationService(model_dir=str(tmp_path / "models"))
    # fewer than 3 paired predictions should raise
    y_true = np.array([1.0, 2.0])
    y_pred = np.array([1.1, 1.9])
    try:
        calib_srv.fit_and_save(
            "Short Player", y_true=y_true, y_pred=y_pred, method="isotonic"
        )
        raised = False
    except ValueError:
        raised = True
    assert raised, "Expected ValueError when trying to fit calibrator with < 3 samples"


def test_calibrator_persist_and_load_roundtrip(tmp_path):
    from backend.services.calibration_service import CalibrationService

    models_dir = tmp_path / "models"
    models_dir.mkdir()
    calib_srv = CalibrationService(model_dir=str(models_dir))

    # synthetic data with >=3 samples
    y_true = np.array([0.0, 1.0, 0.0, 1.0])
    y_pred = np.array([0.1, 0.9, 0.2, 0.8])

    result = calib_srv.fit_and_save(
        "Roundtrip Player", y_true=y_true, y_pred=y_pred, method="isotonic"
    )
    assert result is not None

    # load calibrator and apply
    loaded = calib_srv.load_calibrator("Roundtrip Player")
    assert loaded is not None
    try:
        out = loaded.predict(y_pred)
    except Exception:
        out = None
    assert (
        out is not None
    ), "Loaded calibrator should be callable and return predictions"
