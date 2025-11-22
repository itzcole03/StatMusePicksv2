"""Random Forest model wrapper for training, prediction and persistence.

Provides: RandomForestModel class with train/predict/save/load and
feature importance extraction.
"""
from typing import Optional, List, Dict
import os
import joblib
import numpy as np
import pandas as pd

try:
    from sklearn.ensemble import RandomForestRegressor
except Exception:  # pragma: no cover - tests require sklearn
    RandomForestRegressor = None


class RandomForestModel:
    def __init__(self, rf_params: Optional[Dict] = None):
        self.rf_params = rf_params or {"n_estimators": 100, "random_state": 0}
        self.model: Optional[RandomForestRegressor] = None

    def train(self, X, y) -> None:
        if RandomForestRegressor is None:
            raise RuntimeError("scikit-learn not available")
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)
        self.model = RandomForestRegressor(**self.rf_params)
        self.model.fit(X.values, np.asarray(list(y)))

    def predict(self, X) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("model not trained")
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)
        return np.asarray(self.model.predict(X.values))

    def save(self, path: str) -> None:
        d = os.path.dirname(path)
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
        joblib.dump(self.model, path)

    @classmethod
    def load(cls, path: str) -> "RandomForestModel":
        inst = cls()
        inst.model = joblib.load(path)
        return inst

    def get_feature_importances(self, feature_names: Optional[List[str]] = None) -> Dict[str, float]:
        if self.model is None:
            raise RuntimeError("model not trained")
        importances = getattr(self.model, "feature_importances_", None)
        if importances is None:
            raise RuntimeError("underlying estimator has no feature_importances_")
        if feature_names is None:
            return {str(i): float(v) for i, v in enumerate(importances)}
        if len(feature_names) != len(importances):
            return {str(i): float(v) for i, v in enumerate(importances)}
        return {fn: float(v) for fn, v in zip(feature_names, importances)}
