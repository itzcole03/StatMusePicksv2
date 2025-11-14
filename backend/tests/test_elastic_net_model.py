import numpy as np
from pathlib import Path

def test_elastic_net_train_predict(tmp_path):
    try:
        from backend.models.elastic_net_model import ElasticNetModel
    except Exception:
        # If sklearn missing, skip the test by raising to pytest
        import pytest

        pytest.skip("sklearn not available")

    # simple synthetic binary classification
    rng = np.random.RandomState(0)
    X = rng.normal(size=(200, 5))
    # make a separable target
    w = np.array([1.0, -0.5, 0.2, 0.0, 0.0])
    logits = X.dot(w) + rng.normal(scale=0.1, size=200)
    y = (logits > 0).astype(int)

    model = ElasticNetModel(C=1.0, l1_ratio=0.5, max_iter=2000, random_state=0)
    model.train(X, y, feature_names=[f"f{i}" for i in range(X.shape[1])])

    probs = model.predict_proba(X)
    assert probs.shape == (200, 2)
    assert (probs >= 0.0).all() and (probs <= 1.0).all()

    preds = model.predict(X)
    assert preds.shape == (200,)

    # save/load roundtrip
    p = tmp_path / "en.joblib"
    model.save(p)
    loaded = ElasticNetModel.load(p)
    lp = loaded.predict_proba(X)
    assert lp.shape == (200, 2)
