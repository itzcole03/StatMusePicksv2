"""Lightweight XGBoost training wrapper with sklearn fallback.

Provides: train_xgboost, predict, save_model, load_model
"""
from typing import Optional, Tuple
import joblib
import numpy as np
import os

HAS_XGB = True
try:
    import xgboost as xgb  # type: ignore
except Exception:
    HAS_XGB = False

if not HAS_XGB:
    # fallback
    from sklearn.ensemble import GradientBoostingRegressor as _SKGB


def train_xgboost(X, y, X_val=None, y_val=None, params: Optional[dict] = None, num_rounds: int = 100, early_stopping_rounds: int = 10):
    """Train an XGBoost or fallback GradientBoostingRegressor.

    Returns the fitted model.
    """
    params = params or {}
    if HAS_XGB:
        model = xgb.XGBRegressor(n_estimators=num_rounds, **params)
        fit_kwargs = {}
        if X_val is not None and y_val is not None:
            fit_kwargs['eval_set'] = [(X_val, y_val)]
            fit_kwargs['verbose'] = False
        # Some xgboost versions accept early_stopping_rounds in fit(), others require callback
        try:
            if X_val is not None and y_val is not None:
                model.fit(X, y, early_stopping_rounds=early_stopping_rounds, **fit_kwargs)
            else:
                model.fit(X, y, **fit_kwargs)
        except TypeError:
            # fallback to callback-based early stopping
            try:
                cb = []
                if X_val is not None and y_val is not None and hasattr(xgb, 'callback'):
                    cb.append(xgb.callback.EarlyStopping(rounds=early_stopping_rounds))
                if cb:
                    model.fit(X, y, callbacks=cb, **fit_kwargs)
                else:
                    model.fit(X, y, **fit_kwargs)
            except Exception:
                # last-resort: regular fit
                model.fit(X, y, **fit_kwargs)
        return model
    else:
        model = _SKGB(n_estimators=num_rounds, **{k: v for k, v in (params or {}).items() if k in ('learning_rate','max_depth','min_samples_leaf','subsample')})
        model.fit(X, y)
        return model


def predict(model, X):
    arr = model.predict(X)
    return np.array(arr)


def save_model(model, path: str):
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)
    joblib.dump(model, path)


def load_model(path: str):
    return joblib.load(path)
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
