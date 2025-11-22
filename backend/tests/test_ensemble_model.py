import numpy as np
import pandas as pd
from backend.models.ensemble_model import EnsembleModel


def test_ensemble_train_predict_and_save(tmp_path):
    rng = np.random.RandomState(1)
    n = 300
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    X = pd.DataFrame({"x1": x1, "x2": x2})
    y = 1.5 * x1 - 2.0 * x2 + rng.normal(scale=0.2, size=n)

    ens = EnsembleModel(rf_params={"n_estimators": 20, "random_state": 0}, en_params={"alpha": 0.1, "l1_ratio": 0.5, "random_state": 0})
    ens.train(X, y)

    preds = ens.predict(X.head(5))
    assert preds.shape[0] == 5

    # feature importances
    fi = ens.get_feature_importances(list(X.columns))
    assert isinstance(fi, dict)
    assert set(fi.keys()) == set(X.columns)

    # save/load
    p = tmp_path / "ens.pkl"
    ens.save(str(p))
    loaded = EnsembleModel.load(str(p))
    preds2 = loaded.predict(X.head(5))
    assert preds2.shape[0] == 5
