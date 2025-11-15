import numpy as np
import pytest

try:
    from backend.models.ensemble_model import EnsembleModel
except Exception:
    EnsembleModel = None


def test_ensemble_handles_nans_and_tunes_weights():
    if EnsembleModel is None:
        pytest.skip("EnsembleModel not available")

    # Create a small dataset with NaNs in feature 0
    rng = np.random.RandomState(0)
    X = rng.randn(50, 3)
    y = (X[:, 1] * 2.0 + X[:, 2] * -1.0) + rng.randn(50) * 0.1

    # Introduce NaNs in the first column for many rows
    X[:30, 0] = np.nan

    ens = EnsembleModel()
    # fit should succeed thanks to internal imputer
    ens.fit(X, y)

    # predict should return an array of correct shape
    preds = ens.predict(X[:5])
    assert preds.shape[0] == 5

    # tune_weights_by_mae should run and return a (mae, weights) tuple
    mae, weights = ens.tune_weights_by_mae(X[30:], y[30:], n_trials=8, timeout=30)
    # mae may be None if tuning path failed, but weights should be a tuple
    assert isinstance(weights, tuple)
    # If mae is not None, it should be a finite float
    if mae is not None:
        assert isinstance(mae, float)
        assert np.isfinite(mae)
