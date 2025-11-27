"""Ensemble model combining a RandomForest and ElasticNet baseline.

Provides a simple averaged ensemble that trains each component and returns
the weighted average prediction. Optional XGBoost support (if installed)
is used when available.
"""

import os
from typing import Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold

try:
    from backend.models.elastic_net_model import ElasticNetModel
except Exception:
    ElasticNetModel = None

try:
    import xgboost as xgb  # type: ignore

    XGBOOST_AVAILABLE = True
except Exception:
    XGBOOST_AVAILABLE = False


class EnsembleModel:
    def __init__(
        self,
        rf_params: Optional[Dict] = None,
        en_params: Optional[Dict] = None,
        weights: Optional[List[float]] = None,
    ):
        self.rf_params = rf_params or {"n_estimators": 100, "random_state": 0}
        self.en_params = en_params or {"alpha": 1.0, "l1_ratio": 0.5, "random_state": 0}
        self.weights = weights

        self.rf: Optional[RandomForestRegressor] = None
        self.en: Optional[object] = None
        self.xgb_model = None

    def _ensure_models(self):
        if self.rf is None:
            self.rf = RandomForestRegressor(**self.rf_params)
        if self.en is None and ElasticNetModel is not None:
            self.en = ElasticNetModel(**self.en_params)

    def train(self, X: pd.DataFrame, y) -> None:
        """Train ensemble components on X,y."""
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)
        self._ensure_models()
        # Train RandomForest
        if self.rf is not None:
            self.rf.fit(X.values, np.asarray(list(y)))
        # Train ElasticNet baseline
        if self.en is not None:
            self.en.train(X, y)
        # Optionally train XGBoost if available
        if XGBOOST_AVAILABLE:
            try:
                dmat = xgb.DMatrix(X.values, label=np.asarray(list(y)))
                params = {"objective": "reg:squarederror", "verbosity": 0}
                self.xgb_model = xgb.train(params, dmat, num_boost_round=50)
            except Exception:
                self.xgb_model = None

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)
        preds = []
        if self.rf is not None:
            preds.append(self.rf.predict(X.values))
        if self.en is not None:
            preds.append(self.en.predict(X))
        if self.xgb_model is not None and XGBOOST_AVAILABLE:
            try:
                dmat = xgb.DMatrix(X.values)
                preds.append(self.xgb_model.predict(dmat))
            except Exception:
                pass

        if not preds:
            raise RuntimeError("No component models available for prediction")

        arr = np.vstack(preds)
        if self.weights and len(self.weights) == arr.shape[0]:
            w = np.asarray(self.weights).reshape(-1, 1)
            res = (arr * w).sum(axis=0) / float(w.sum())
        else:
            res = arr.mean(axis=0)
        return res

    def save(self, path: str) -> None:
        payload = {
            "rf_params": self.rf_params,
            "en_params": self.en_params,
            "weights": self.weights,
            "rf": self.rf,
            "en": self.en,
            "xgb_model": self.xgb_model,
        }
        joblib.dump(payload, path)

    @classmethod
    def load(cls, path: str) -> "EnsembleModel":
        data = joblib.load(path)
        inst = cls(
            rf_params=data.get("rf_params"),
            en_params=data.get("en_params"),
            weights=data.get("weights"),
        )
        inst.rf = data.get("rf")
        inst.en = data.get("en")
        inst.xgb_model = data.get("xgb_model")
        return inst

    def get_feature_importances(
        self, feature_names: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """Return feature importances from RandomForest; if feature_names not provided,
        use indices as strings."""
        if self.rf is None:
            raise RuntimeError("RandomForest not trained")
        importances = self.rf.feature_importances_
        if feature_names is None:
            return {str(i): float(v) for i, v in enumerate(importances)}
        if len(feature_names) != len(importances):
            return {str(i): float(v) for i, v in enumerate(importances)}
        return {fn: float(v) for fn, v in zip(feature_names, importances)}


class StackingEnsemble:
    """Simple stacking ensemble that trains base learners and a Ridge meta-learner.

    Usage: instantiate with base model factories or prebuilt sklearn estimators,
    call `train(X, y)` then `predict(X)`.
    """

    def __init__(
        self, base_models: Optional[List] = None, meta_model=None, n_folds: int = 5
    ):
        # base_models: list of (name, estimator) tuples
        self.base_models = base_models or []
        self.meta_model = meta_model or Ridge(alpha=1.0)
        self.n_folds = int(n_folds)
        self.fitted = False

    def train(self, X, y):
        import numpy as _np

        if not isinstance(X, (list, tuple)):
            import pandas as _pd

            if not isinstance(X, _pd.DataFrame):
                X = _pd.DataFrame(X)

        X_vals = X.values if hasattr(X, "values") else _np.asarray(X)
        y_vals = _np.asarray(list(y))

        # Out-of-fold predictions for meta training
        oof_preds = _np.zeros((X_vals.shape[0], len(self.base_models)))
        kf = KFold(n_splits=self.n_folds, shuffle=True, random_state=0)
        for fold_idx, (tr_idx, val_idx) in enumerate(kf.split(X_vals)):
            X_tr, X_val = X_vals[tr_idx], X_vals[val_idx]
            y_tr = y_vals[tr_idx]
            for m_idx, (_name, estimator) in enumerate(self.base_models):
                est = estimator
                try:
                    est.fit(X_tr, y_tr)
                    oof_preds[val_idx, m_idx] = est.predict(X_val)
                except Exception:
                    # fallback: zeros
                    oof_preds[val_idx, m_idx] = 0.0

        # Fit meta-learner on OOF preds
        self.meta_model.fit(oof_preds, y_vals)

        # Refit base models on full data for serving
        for m_idx, (_name, estimator) in enumerate(self.base_models):
            try:
                estimator.fit(X_vals, y_vals)
            except Exception:
                pass

        self.fitted = True

    def predict(self, X):
        import numpy as _np

        if not self.fitted:
            raise RuntimeError("StackingEnsemble not trained")
        import pandas as _pd

        if not isinstance(X, _pd.DataFrame):
            X = _pd.DataFrame(X)
        X_vals = X.values
        preds = _np.vstack([est.predict(X_vals) for _name, est in self.base_models])
        # shape (n_models, n_samples) -> transpose to (n_samples, n_models)
        preds_t = preds.T
        meta_preds = self.meta_model.predict(preds_t)
        return meta_preds

    def save(self, path: str):
        d = os.path.dirname(path)
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
        joblib.dump(
            {
                "base_models": self.base_models,
                "meta_model": self.meta_model,
                "n_folds": self.n_folds,
                "fitted": self.fitted,
            },
            path,
        )

    @classmethod
    def load(cls, path: str):
        data = joblib.load(path)
        inst = cls(
            base_models=data.get("base_models"),
            meta_model=data.get("meta_model"),
            n_folds=data.get("n_folds", 5),
        )
        inst.fitted = data.get("fitted", False)
        return inst
