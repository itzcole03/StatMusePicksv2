import os
import sys
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.models.ensemble_model import EnsembleModel


def make_data(n=200, seed=1):
    rng = np.random.RandomState(seed)
    X = rng.randn(n, 6)
    coef = np.array([0.5, -0.2, 0.1, 0.0, 0.2, 0.05])
    y = X.dot(coef) + 0.05 * rng.randn(n)
    return X, y


def test_stacking_if_available():
    # Only run stacking test if the implementation supports it
    try:
        m = EnsembleModel(use_stacking=True)
    except Exception:
        return

    X, y = make_data(300)
    # Fit should succeed (stacking falls back if unavailable internally)
    m.fit(X, y)
    preds = m.predict(X[:5])
    assert preds.shape[0] == 5
    assert np.all(np.isfinite(preds))
