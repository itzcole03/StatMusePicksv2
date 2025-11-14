import numpy as np
import pytest

try:
    import xgboost  # noqa: F401
    XGBOOST_AVAILABLE = True
except Exception:
    XGBOOST_AVAILABLE = False

from backend.models.xgboost_model import XGBoostModel


@pytest.mark.skipif(not XGBOOST_AVAILABLE, reason="xgboost not installed")
def test_regression_xgb_train_predict():
    rng = np.random.RandomState(1)
    X = rng.randn(80, 4)
    coef = np.array([0.5, -1.0, 0.2, 0.0])
    y = X.dot(coef) + rng.randn(80) * 0.05

    m = XGBoostModel(task="regression", n_estimators=10, max_depth=3, random_state=0)
    m.train(X, y, feature_names=[f"f{i}" for i in range(X.shape[1])])
    preds = m.predict(X)
    assert preds.shape[0] == X.shape[0]
    fi = m.feature_importances()
    assert isinstance(fi, dict)
    assert len(fi) == X.shape[1]


@pytest.mark.skipif(not XGBOOST_AVAILABLE, reason="xgboost not installed")
def test_classification_xgb_train_predict():
    from sklearn.datasets import make_classification

    X, y = make_classification(n_samples=120, n_features=5, n_informative=3, random_state=2)
    m = XGBoostModel(task="classification", n_estimators=10, max_depth=3, random_state=0)
    m.train(X, y, feature_names=[f"f{i}" for i in range(X.shape[1])])
    preds = m.predict(X)
    assert preds.shape[0] == X.shape[0]
    probs = m.predict_proba(X)
    assert probs.shape[0] == X.shape[0]
    fi = m.feature_importances()
    assert isinstance(fi, dict)
    assert len(fi) == X.shape[1]
