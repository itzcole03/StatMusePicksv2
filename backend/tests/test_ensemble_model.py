import os
import sys
import numpy as np

# Ensure repository root is on sys.path so `backend` imports succeed when
# running tests from arbitrary working directories.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.models.ensemble_model import EnsembleModel


def make_data(n=200, seed=0):
    rng = np.random.RandomState(seed)
    X = rng.randn(n, 6)
    coef = np.array([1.0, -0.5, 0.2, 0.0, 0.3, 0.1])
    y = X.dot(coef) + 0.1 * rng.randn(n)
    return X, y


def test_ensemble_fit_predict_and_save(tmp_path):
    X, y = make_data(200)
    model = EnsembleModel()
    # basic fit
    model.fit(X, y)

    # predict on a small batch
    Xp = X[:10]
    preds = model.predict(Xp)
    assert preds.shape[0] == Xp.shape[0]
    assert np.all(np.isfinite(preds))

    # save and load
    p = tmp_path / "ensemble_test.pkl"
    model.save(str(p))
    loaded = EnsembleModel.load(str(p))
    preds2 = loaded.predict(Xp)
    # predictions should match after save/load
    assert np.allclose(preds, preds2)
