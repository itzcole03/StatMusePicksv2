import numpy as np
import pandas as pd

from backend.models.random_forest_model import RandomForestModel


def test_random_forest_train_predict(tmp_path):
    # synthetic dataset: 100 rows, 5 features
    rng = np.random.RandomState(1)
    X = pd.DataFrame(rng.randn(100, 5), columns=[f"f{i}" for i in range(5)])
    coef = np.array([0.5, -0.2, 0.1, 0.0, 0.3])
    y = X.values.dot(coef) + rng.normal(scale=0.1, size=100)

    model = RandomForestModel(rf_params={"n_estimators": 10, "random_state": 42})
    model.train(X, y)

    preds = model.predict(X)
    assert preds.shape[0] == X.shape[0]

    # feature importances should return a mapping with 5 entries
    imps = model.get_feature_importances(feature_names=list(X.columns))
    assert isinstance(imps, dict)
    assert len(imps) == 5

    # save and load
    out = tmp_path / "rf_test.pkl"
    model.save(str(out))
    loaded = RandomForestModel.load(str(out))
    loaded_preds = loaded.predict(X)
    assert loaded_preds.shape[0] == X.shape[0]
