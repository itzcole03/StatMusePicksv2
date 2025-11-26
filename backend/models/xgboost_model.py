"""Lightweight XGBoost model wrapper with train/predict/save/load.

Falls back gracefully when `xgboost` is not installed.
"""
from typing import Optional
import joblib
import numpy as np
import pandas as pd

try:
    import xgboost as xgb  # type: ignore
    XGBOOST_AVAILABLE = True
except Exception:
    xgb = None
    XGBOOST_AVAILABLE = False


class XGBoostModel:
    def __init__(self, params: Optional[dict] = None, num_boost_round: int = 100):
        if not XGBOOST_AVAILABLE:
            raise ImportError("xgboost is not available in this environment")
        # sensible default hyperparameters used when none provided
        default = {
            "objective": "reg:squarederror",
            "verbosity": 0,
            "n_estimators": 200,
            "max_depth": 6,
            "learning_rate": 0.05,
            "subsample": 0.9,
            "colsample_bytree": 0.8,
        }
        self.params = {**default, **(params or {})}
        self.num_boost_round = int(num_boost_round)
        self.booster = None

    def train(self, X: pd.DataFrame, y, eval_set: Optional[tuple] = None, early_stopping_rounds: Optional[int] = None):
        if not XGBOOST_AVAILABLE:
            raise ImportError("xgboost is not available in this environment")
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)
        dtrain = xgb.DMatrix(X.values, label=np.asarray(list(y)))
        evallist = []
        if eval_set is not None:
            X_val, y_val = eval_set
            dval = xgb.DMatrix(pd.DataFrame(X_val).values, label=np.asarray(list(y_val)))
            evallist = [(dval, 'eval')]
        self.booster = xgb.train(self.params, dtrain, num_boost_round=self.num_boost_round, evals=evallist, early_stopping_rounds=early_stopping_rounds)

    def predict(self, X: pd.DataFrame):
        if not XGBOOST_AVAILABLE:
            raise ImportError("xgboost is not available in this environment")
        if self.booster is None:
            raise RuntimeError("model not trained or loaded")
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)
        dmat = xgb.DMatrix(X.values)
        return self.booster.predict(dmat)

    def compute_shap(self, X: pd.DataFrame):
        """Compute SHAP values for given `X` if `shap` is available.

        Returns a tuple (expected_value, shap_values) or (None, None) when
        shap is not installed or the model isn't trained.
        """
        try:
            import shap  # type: ignore
        except Exception:
            return None, None

        if self.booster is None:
            return None, None

        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)

        # Use TreeExplainer for XGBoost boosters
        try:
            explainer = shap.TreeExplainer(self.booster)
            dmat = xgb.DMatrix(X.values)
            shap_values = explainer.shap_values(X.values)
            expected = explainer.expected_value
            return expected, shap_values
        except Exception:
            return None, None

    def save(self, path: str):
        joblib.dump({"params": self.params, "num_boost_round": self.num_boost_round, "booster": self.booster}, path)

    @classmethod
    def load(cls, path: str):
        data = joblib.load(path)
        inst = cls(params=data.get("params"), num_boost_round=data.get("num_boost_round", 100))
        inst.booster = data.get("booster")
        return inst
