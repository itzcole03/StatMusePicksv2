import numpy as np
import pandas as pd
import tempfile
from backend.models.elastic_net_model import ElasticNetModel


def test_elastic_net_train_predict_and_save_load(tmp_path):
    # create a simple linear dataset: y = 2*x1 - 3*x2 + noise
    rng = np.random.RandomState(0)
    n = 200
    x1 = rng.normal(loc=0.0, scale=1.0, size=n)
    x2 = rng.normal(loc=0.0, scale=1.0, size=n)
    X = pd.DataFrame({"x1": x1, "x2": x2})
    y = 2.0 * x1 - 3.0 * x2 + rng.normal(scale=0.1, size=n)

    model = ElasticNetModel(alpha=0.1, l1_ratio=0.5, random_state=0)
    model.train(X, y)

    # predict on first 5 rows
    preds = model.predict(X.head(5))
    assert preds.shape[0] == 5

    # coefficients mapping
    coefs = model.get_coefficients(list(X.columns))
    assert isinstance(coefs, dict)
    assert set(coefs.keys()) == set(X.columns)

    # save & load
    p = tmp_path / "en_model.joblib"
    model.save(str(p))
    loaded = ElasticNetModel.load(str(p))
    preds2 = loaded.predict(X.head(5))
    assert preds2.shape[0] == 5
