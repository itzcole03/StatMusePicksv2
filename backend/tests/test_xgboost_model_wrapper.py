import pytest
from backend.models import xgboost_model


def test_xgboost_wrapper_import_or_skip():
    if not getattr(xgboost_model, 'XGBOOST_AVAILABLE', False):
        with pytest.raises(ImportError):
            xgboost_model.XGBoostModel()
    else:
        # basic smoke: instantiate (no training here)
        m = xgboost_model.XGBoostModel(num_boost_round=5)
        assert m is not None
