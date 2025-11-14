from __future__ import annotations

from typing import Optional, Sequence, Dict, Any

import joblib
import numpy as np
from pathlib import Path


class ElasticNetModel:
    """Simple wrapper around sklearn LogisticRegression with elasticnet penalty.

    This wrapper provides a consistent train/predict/save API similar to other
    model wrappers in `backend/models/`.
    """

    def __init__(
        self,
        C: float = 1.0,
        l1_ratio: float = 0.5,
        max_iter: int = 5000,
        random_state: int = 0,
    ) -> None:
        self.C = float(C)
        self.l1_ratio = float(l1_ratio)
        self.max_iter = int(max_iter)
        self.random_state = int(random_state)
        self._model = None
        self.feature_names: Optional[Sequence[str]] = None

    def train(self, X, y, feature_names: Optional[Sequence[str]] = None):
        from sklearn.linear_model import LogisticRegression

        arrX = np.asarray(X)
        arry = np.asarray(y)
        self.feature_names = list(feature_names) if feature_names is not None else None
        self._model = LogisticRegression(
            penalty="elasticnet",
            solver="saga",
            C=self.C,
            l1_ratio=self.l1_ratio,
            max_iter=self.max_iter,
            random_state=self.random_state,
        )
        self._model.fit(arrX, arry)

    def predict(self, X):
        if self._model is None:
            raise RuntimeError("Model not trained")
        return self._model.predict(np.asarray(X))

    def predict_proba(self, X):
        if self._model is None:
            raise RuntimeError("Model not trained")
        if not hasattr(self._model, "predict_proba"):
            raise RuntimeError("Underlying estimator does not support predict_proba")
        return self._model.predict_proba(np.asarray(X))

    def coef_(self):
        if self._model is None:
            return None
        return getattr(self._model, "coef_", None)

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self._model, "meta": self._meta_dict()}, str(p))

    @classmethod
    def load(cls, path: str | Path) -> "ElasticNetModel":
        obj = joblib.load(str(path))
        meta = obj.get("meta", {})
        inst = cls(
            C=meta.get("C", 1.0),
            l1_ratio=meta.get("l1_ratio", 0.5),
            max_iter=meta.get("max_iter", 5000),
            random_state=meta.get("random_state", 0),
        )
        inst._model = obj.get("model")
        inst.feature_names = meta.get("feature_names")
        return inst

    def _meta_dict(self) -> Dict[str, Any]:
        return {
            "C": self.C,
            "l1_ratio": self.l1_ratio,
            "max_iter": self.max_iter,
            "random_state": self.random_state,
            "feature_names": list(self.feature_names) if self.feature_names is not None else None,
        }

    def get_estimator(self):
        return self._model
