import numpy as np

from backend.models.random_forest_model import RandomForestModel


def test_regression_train_predict():
    # synthetic regression data
    rng = np.random.RandomState(0)
    X = rng.randn(100, 5)
    coef = np.array([1.2, -0.5, 0.0, 0.7, 0.3])
    y = X.dot(coef) + rng.randn(100) * 0.1

    m = RandomForestModel(task="regression", n_estimators=10, random_state=0)
    m.train(X, y, feature_names=[f"f{i}" for i in range(X.shape[1])])
    preds = m.predict(X)
    assert preds.shape[0] == X.shape[0]
    fi = m.feature_importances()
    assert isinstance(fi, dict)
    assert len(fi) == X.shape[1]


def test_classification_train_predict():
    # synthetic classification data
    from sklearn.datasets import make_classification

    X, y = make_classification(n_samples=200, n_features=6, n_informative=3, random_state=0)
    m = RandomForestModel(task="classification", n_estimators=10, random_state=0)
    m.train(X, y, feature_names=[f"f{i}" for i in range(X.shape[1])])
    preds = m.predict(X)
    assert preds.shape[0] == X.shape[0]
    probs = m.predict_proba(X)
    assert probs.shape[0] == X.shape[0]
    fi = m.feature_importances()
    assert isinstance(fi, dict)
    assert len(fi) == X.shape[1]
