import pytest
import numpy as np
from backend.services import xgboost_wrapper as wb


def test_xgboost_wrapper_smoke():
    assert hasattr(wb, 'XGBoostWrapper')
    if not wb.XGBoostWrapper.available:
        pytest.skip('xgboost not installed; skipping integration smoke')

    X = np.random.RandomState(0).rand(20, 5)
    y = np.random.RandomState(1).rand(20)

    wrapper = wb.XGBoostWrapper(n_estimators=1, use_label_encoder=False, eval_metric='rmse')
    model = wrapper.fit(X, y)
    preds = wrapper.predict(X)
    assert len(preds) == X.shape[0]
