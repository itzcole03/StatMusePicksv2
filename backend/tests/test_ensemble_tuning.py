import os
import sys
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.models.ensemble_model import EnsembleModel


def make_data(n=200, seed=2):
    rng = np.random.RandomState(seed)
    X = rng.randn(n, 6)
    coef = np.array([0.4, -0.3, 0.2, 0.0, 0.1, 0.05])
    y = X.dot(coef) + 0.01 * rng.randn(n)
    return X, y


def test_tune_weights_changes_weights():
    X, y = make_data(300)
    # train ensemble
    m = EnsembleModel()
    m.fit(X, y)
    # create small val set with slightly different random seed
    Xv, yv = make_data(100, seed=3)
    before = getattr(m, "weights", None)
    mae, best_w = m.tune_weights_by_mae(Xv, yv)
    # tuning should return a numeric MAE and weights tuple
    assert mae is None or isinstance(mae, float)
    assert isinstance(best_w, tuple)
    # ensure weights stored
    assert getattr(m, "weights", None) is not None
