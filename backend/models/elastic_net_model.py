"""Elastic Net model wrapper used as a simple baseline regressor.

Provides: train(X, y), predict(X), save(path), load(path), get_coefficients(feature_names=None)

Uses a sklearn Pipeline with `StandardScaler` + `ElasticNet` for stable behaviour.
"""

from typing import Dict, Iterable, List, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


class ElasticNetModel:
    def __init__(
        self,
        alpha: float = 1.0,
        l1_ratio: float = 0.5,
        random_state: Optional[int] = 42,
    ):
        self.alpha = float(alpha)
        self.l1_ratio = float(l1_ratio)
        self.random_state = random_state
        self.pipeline: Optional[Pipeline] = None

    def train(self, X: pd.DataFrame, y: Iterable[float]) -> None:
        """Train an ElasticNet on the provided features `X` and target `y`.

        X should be a pandas DataFrame. `y` can be any iterable convertible to 1d array.
        """
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)

        en = ElasticNet(
            alpha=self.alpha,
            l1_ratio=self.l1_ratio,
            random_state=self.random_state,
            max_iter=5000,
        )
        self.pipeline = Pipeline([("scaler", StandardScaler()), ("est", en)])
        self.pipeline.fit(X.values, np.asarray(list(y)))

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Return predicted numeric values for rows in `X`.

        Accepts pandas DataFrame or array-like. Returns numpy array.
        """
        if self.pipeline is None:
            raise RuntimeError("model is not trained or loaded")
        if not isinstance(X, (pd.DataFrame, pd.Series)):
            X = pd.DataFrame(X)
        return self.pipeline.predict(X.values)

    def save(self, path: str) -> None:
        if self.pipeline is None:
            raise RuntimeError("no model to save")
        joblib.dump(
            {
                "alpha": self.alpha,
                "l1_ratio": self.l1_ratio,
                "random_state": self.random_state,
                "pipeline": self.pipeline,
            },
            path,
        )

    @classmethod
    def load(cls, path: str) -> "ElasticNetModel":
        data = joblib.load(path)
        inst = cls(
            alpha=data.get("alpha", 1.0),
            l1_ratio=data.get("l1_ratio", 0.5),
            random_state=data.get("random_state", None),
        )
        inst.pipeline = data.get("pipeline")
        return inst

    def get_coefficients(
        self, feature_names: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """Return a mapping feature -> coefficient. If `feature_names` omitted,
        return numeric-index keys as strings.
        """
        if self.pipeline is None:
            raise RuntimeError("model is not trained or loaded")
        est: ElasticNet = self.pipeline.named_steps["est"]
        coefs = est.coef_
        if feature_names is None:
            return {str(i): float(c) for i, c in enumerate(coefs)}
        if len(feature_names) != len(coefs):
            # fall back to positional mapping
            return {str(i): float(c) for i, c in enumerate(coefs)}
        return {fn: float(c) for fn, c in zip(feature_names, coefs)}
