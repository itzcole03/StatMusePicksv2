from __future__ import annotations

from typing import Optional, Sequence, Dict, Any

import joblib
import numpy as np
from pathlib import Path

try:
    from xgboost import XGBRegressor, XGBClassifier
except Exception:
    XGBRegressor = None
    XGBClassifier = None


class XGBoostModel:
    """Wrapper around XGBoost regressor/classifier with save/load and feature importances."""

    def __init__(
        self,
        task: str = "regression",
        n_estimators: int = 100,
        max_depth: int = 6,
        learning_rate: float = 0.1,
        subsample: float = 1.0,
        random_state: int = 0,
        n_jobs: int = -1,
    ) -> None:
        self.task = task
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.subsample = subsample
        self.random_state = random_state
        self.n_jobs = n_jobs
        self._model = None
        self.feature_names: Optional[Sequence[str]] = None

    def _build(self):
        if self.task == "regression":
            if XGBRegressor is None:
                raise RuntimeError("xgboost not installed")
            return XGBRegressor(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                learning_rate=self.learning_rate,
                subsample=self.subsample,
                random_state=self.random_state,
                n_jobs=self.n_jobs,
                verbosity=0,
            )
        else:
            if XGBClassifier is None:
                raise RuntimeError("xgboost not installed")
            return XGBClassifier(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                learning_rate=self.learning_rate,
                subsample=self.subsample,
                random_state=self.random_state,
                n_jobs=self.n_jobs,
                use_label_encoder=False,
                verbosity=0,
            )

    def train(self, X, y, feature_names: Optional[Sequence[str]] = None, early_stopping_rounds: Optional[int] = None):
        arrX = np.asarray(X)
        arry = np.asarray(y)
        self.feature_names = list(feature_names) if feature_names is not None else None
        self._model = self._build()
        if early_stopping_rounds is not None and hasattr(self._model, "fit"):
            # no eval_set by default; user can pass small val split externally if desired
            self._model.fit(arrX, arry)
        else:
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

    def feature_importances(self) -> Optional[Dict[str, float]]:
        if self._model is None:
            return None
        if not hasattr(self._model, "feature_importances_"):
            return None
        fi = getattr(self._model, "feature_importances_")
        if self.feature_names is None or len(self.feature_names) != len(fi):
            return {str(i): float(v) for i, v in enumerate(fi)}
        return {n: float(v) for n, v in zip(self.feature_names, fi)}

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self._model, "meta": self._meta_dict()}, str(p))

    @classmethod
    def load(cls, path: str | Path) -> "XGBoostModel":
        obj = joblib.load(str(path))
        meta = obj.get("meta", {})
        inst = cls(
            task=meta.get("task", "regression"),
            n_estimators=meta.get("n_estimators", 100),
            max_depth=meta.get("max_depth", 6),
            learning_rate=meta.get("learning_rate", 0.1),
            subsample=meta.get("subsample", 1.0),
            random_state=meta.get("random_state", 0),
            n_jobs=meta.get("n_jobs", -1),
        )
        inst._model = obj.get("model")
        inst.feature_names = meta.get("feature_names")
        return inst

    def _meta_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task,
            "n_estimators": self.n_estimators,
            "max_depth": self.max_depth,
            "learning_rate": self.learning_rate,
            "subsample": self.subsample,
            "random_state": self.random_state,
            "n_jobs": self.n_jobs,
            "feature_names": list(self.feature_names) if self.feature_names is not None else None,
        }
