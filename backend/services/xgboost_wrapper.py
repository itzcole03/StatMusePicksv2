try:
    import xgboost as xgb
except Exception:
    xgb = None

from sklearn.base import BaseEstimator, RegressorMixin


class XGBoostWrapper(BaseEstimator, RegressorMixin):
    """Scikit-learn compatible wrapper around XGBoost regressor.

    Implements `get_params`/`set_params` so it can be used in `VotingRegressor`
    and other sklearn utilities even when XGBoost is not importable in all
    environments.
    """

    available = xgb is not None
    _estimator_type = "regressor"

    def __init__(self, **kwargs):
        self.params = kwargs or {}
        self.model = None

    def fit(self, X, y, **fit_kwargs):
        if not self.available:
            raise RuntimeError("xgboost is not installed in the environment")
        # instantiate with params to ensure clone() works on the wrapper
        self.model = xgb.XGBRegressor(**self.params)
        # pass through any fit kwargs to underlying fit
        self.model.fit(X, y, **fit_kwargs)
        return self

    def predict(self, X):
        if self.model is None:
            raise RuntimeError("Model not fitted yet")
        return self.model.predict(X)

    def get_params(self, deep=True):
        return dict(self.params)

    def set_params(self, **params):
        self.params.update(params)
        return self
