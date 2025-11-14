import pytest
import numpy as np

optuna = pytest.importorskip("optuna")

from backend.models.ensemble_model import EnsembleModel


def test_ensemble_optuna_path_runs_and_returns_weights():
    rng = np.random.RandomState(0)
    X = rng.normal(size=(60, 4))
    # create a simple linear-ish target
    y = X[:, 0] * 0.5 + X[:, 1] * -0.3 + rng.normal(scale=0.01, size=X.shape[0])

    ens = EnsembleModel()
    ens.fit(X, y)

    # run a small Optuna search (kept small in tests)
    best_mae, best_w = ens.tune_weights_by_mae(X, y, n_trials=5, timeout=10)

    assert best_mae is not None
    assert isinstance(best_mae, float)
    assert isinstance(best_w, tuple)
    assert len(best_w) in (2, 3)
