import numpy as np
import tempfile
import os

from backend.services.calibration_service import CalibrationService


def test_fit_and_persist_linear_calibrator(tmp_path):
    # synthetic linear relation y = 2*x + 3 + noise
    rng = np.random.RandomState(42)
    x = np.linspace(1, 10, 50)
    noise = rng.normal(scale=0.5, size=x.shape)
    y_true = 2.0 * x + 3.0 + noise
    y_pred = x.copy()  # model underestimates slope

    models_dir = tmp_path / 'models'
    cs = CalibrationService(model_dir=str(models_dir))

    res = cs.fit_and_save('Test Player', y_true=y_true, y_pred=y_pred, method='linear')
    assert 'before' in res and 'after' in res
    assert res['after']['rmse'] <= res['before']['rmse']

    # persisted calibrator should be loadable and transform values
    calib = cs.load_calibrator('Test Player')
    assert calib is not None
    pred_sample = np.array([1.0, 5.0, 10.0])
    out = cs.calibrate('Test Player', pred_sample)
    assert len(out) == len(pred_sample)


def test_fit_and_persist_isotonic_calibrator(tmp_path):
    rng = np.random.RandomState(1)
    x = np.linspace(1, 20, 60)
    noise = rng.normal(scale=1.0, size=x.shape)
    y_true = 0.5 * x + noise
    y_pred = 0.5 * x + 5.0  # biased offset

    models_dir = tmp_path / 'models2'
    cs = CalibrationService(model_dir=str(models_dir))

    res = cs.fit_and_save('Test Player Iso', y_true=y_true, y_pred=y_pred, method='isotonic')
    assert 'before' in res and 'after' in res
    # After calibration the RMSE should not increase substantially
    assert res['after']['rmse'] <= res['before']['rmse'] * 1.1

    calib = cs.load_calibrator('Test Player Iso')
    assert calib is not None
    out = cs.calibrate('Test Player Iso', np.array([1.0, 10.0, 20.0]))
    assert len(out) == 3
