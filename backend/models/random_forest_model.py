from __future__ import annotations

from typing import Optional, Sequence, Dict, Any

import joblib
import numpy as np
from pathlib import Path

from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier


class RandomForestModel:
    """Lightweight wrapper for RandomForest regressor/classifier.

    Supports training, prediction, feature importance extraction, and save/load.
    """

    def __init__(
        self,
        task: str = "regression",
        n_estimators: int = 100,
        max_depth: Optional[int] = None,
        min_samples_split: int = 2,
        min_samples_leaf: int = 1,
        random_state: int = 0,
        n_jobs: int = -1,
    ) -> None:
        self.task = task
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.min_samples_leaf = min_samples_leaf
        self.random_state = random_state
        self.n_jobs = n_jobs
        self._model = None
        self.feature_names: Optional[Sequence[str]] = None

    def _build(self):
        if self.task == "regression":
            return RandomForestRegressor(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                min_samples_split=self.min_samples_split,
                min_samples_leaf=self.min_samples_leaf,
                random_state=self.random_state,
                n_jobs=self.n_jobs,
            )
        else:
            return RandomForestClassifier(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                min_samples_split=self.min_samples_split,
                min_samples_leaf=self.min_samples_leaf,
                random_state=self.random_state,
                n_jobs=self.n_jobs,
            )

    def train(self, X, y, feature_names: Optional[Sequence[str]] = None):
        """Train the model on arrays or array-like features.

        Args:
            X: 2D array-like of shape (n_samples, n_features)
            y: 1D array-like of labels/targets
            feature_names: optional sequence of feature names
        """
        arrX = np.asarray(X)
        arry = np.asarray(y)
        self.feature_names = list(feature_names) if feature_names is not None else None
        self._model = self._build()
        self._model.fit(arrX, arry)

    def predict(self, X):
        if self._model is None:
            raise RuntimeError("Model not trained")
        arrX = np.asarray(X)
        return self._model.predict(arrX)

    def predict_proba(self, X):
        if self._model is None:
            raise RuntimeError("Model not trained")
        if not hasattr(self._model, "predict_proba"):
            raise RuntimeError("Underlying estimator does not support predict_proba")
        arrX = np.asarray(X)
        return self._model.predict_proba(arrX)

    def feature_importances(self) -> Optional[Dict[str, float]]:
        if self._model is None:
            return None
        if not hasattr(self._model, "feature_importances_"):
            return None
        fi = getattr(self._model, "feature_importances_")
        if self.feature_names is None:
            # return unnamed indices
            return {str(i): float(v) for i, v in enumerate(fi)}
        if len(self.feature_names) != len(fi):
            return {str(i): float(v) for i, v in enumerate(fi)}
        return {n: float(v) for n, v in zip(self.feature_names, fi)}

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self._model, "meta": self._meta_dict()}, str(p))

    @classmethod
    def load(cls, path: str | Path) -> "RandomForestModel":
        obj = joblib.load(str(path))
        meta = obj.get("meta", {})
        inst = cls(
            task=meta.get("task", "regression"),
            n_estimators=meta.get("n_estimators", 100),
            max_depth=meta.get("max_depth", None),
            min_samples_split=meta.get("min_samples_split", 2),
            min_samples_leaf=meta.get("min_samples_leaf", 1),
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
            "min_samples_split": self.min_samples_split,
            "min_samples_leaf": self.min_samples_leaf,
            "random_state": self.random_state,
            "n_jobs": self.n_jobs,
            "feature_names": list(self.feature_names) if self.feature_names is not None else None,
        }
