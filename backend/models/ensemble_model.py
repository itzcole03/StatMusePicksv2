"""Ensemble model wrappers.

Provides a simple VotingRegressor ensemble combining Random Forest,
XGBoost (if available), and ElasticNet, plus an optional stacking
implementation using a Ridge meta-learner.

This file is intentionally lightweight and uses sklearn defaults so it
can be used in the dev environment even if project-specific model
wrappers are not importable. It exposes a simple API: `fit`, `predict`,
`save`, `load`.
"""
from __future__ import annotations

import os
from typing import List, Tuple, Optional

import joblib
import numpy as np

from sklearn.ensemble import VotingRegressor
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline

try:
    from xgboost import XGBRegressor  # type: ignore
    _XGB_AVAILABLE = True
except Exception:
    _XGB_AVAILABLE = False

try:
    from sklearn.ensemble import StackingRegressor
    _STACKING_AVAILABLE = True
except Exception:
    _STACKING_AVAILABLE = False


class EnsembleModel:
    """Simple ensemble wrapper.

    Parameters
    - weights: tuple of weights for the base estimators in order
      (random_forest, xgboost, elastic_net). If xgboost isn't
      available the provided weights will be re-normalized.
    - use_stacking: if True and sklearn provides `StackingRegressor`,
      use a stacking ensemble with a Ridge meta-learner instead of
      VotingRegressor.
    """

    def __init__(self, weights: Tuple[float, float, float] = (0.4, 0.4, 0.2), use_stacking: bool = False):
        self.weights = weights
        self.use_stacking = use_stacking and _STACKING_AVAILABLE
        self.model = None

    def _build_estimators(self) -> List[Tuple[str, object]]:
        estimators: List[Tuple[str, object]] = []

        # Random Forest
        estimators.append(("rf", RandomForestRegressor(n_estimators=150, max_depth=10, random_state=42)))

        # XGBoost if available
        if _XGB_AVAILABLE:
            estimators.append(("xgb", XGBRegressor(n_estimators=150, max_depth=6, learning_rate=0.05, verbosity=0, random_state=42)))

        # Elastic Net (wrap in pipeline to ensure shape compatibility)
        estimators.append(("en", Pipeline([("en", ElasticNet(alpha=1.0, l1_ratio=0.5))])))

        return estimators

    def fit(self, X, y):
        """Fit the ensemble to training data.

        X: array-like or DataFrame
        y: array-like targets
        """
        estimators = self._build_estimators()

        # Determine weights for the estimators we actually built
        base_names = [name for name, _ in estimators]

        # Map requested weights to the actual built estimators order
        requested = list(self.weights)
        # If xgboost not available, drop second weight and renormalize
        if not _XGB_AVAILABLE:
            # requested corresponds to rf,xgb,en -> drop xgb
            requested = [requested[0], requested[2]]

        # Ensure length matches
        if len(requested) != len(estimators):
            # fallback: equal weights
            weights = [1.0 / len(estimators)] * len(estimators)
        else:
            total = float(sum(requested))
            weights = [w / total if total > 0 else 1.0 / len(requested) for w in requested]

        if self.use_stacking and _STACKING_AVAILABLE:
            from sklearn.ensemble import StackingRegressor

            self.model = StackingRegressor(estimators=estimators, final_estimator=Ridge())
        else:
            # VotingRegressor expects (name, estimator) pairs
            self.model = VotingRegressor(estimators=estimators, weights=weights)

        self.model.fit(X, y)
        return self

    def predict(self, X):
        if self.model is None:
            raise RuntimeError("Model not fitted")
        return self.model.predict(X)

    def tune_weights_by_mae(self, X_val, y_val, candidate_weights: Optional[List[Tuple[float, float, float]]] = None, n_trials: int = 50, timeout: Optional[int] = None) -> Tuple[Optional[float], Tuple[float, ...]]:
        """Tune ensemble base-estimator weights to minimize MAE on validation data.

        This method prefers an Optuna-based search when `optuna` is available in the
        environment. If Optuna is not available, it falls back to evaluating the
        provided `candidate_weights` (or a small default candidate set).

        Parameters
        - X_val, y_val: validation set to evaluate MAE
        - candidate_weights: optional list of candidate tuples. If provided and
          Optuna is not available, these will be evaluated.
        - n_trials: number of Optuna trials to run when Optuna is present.
        - timeout: optional timeout (seconds) passed to `study.optimize`.

        Returns (best_mae, best_weights). If stacking is used, returns (None, current_weights).
        """
        from sklearn.metrics import mean_absolute_error

        if self.model is None:
            raise RuntimeError("Model not fitted")

        # Stacking doesn't use weights in the same way
        if self.use_stacking:
            return None, tuple(getattr(self, "weights", ()))

        # Helper to evaluate a candidate weight vector (already normalized)
        def _eval_weights(w_tuple) -> Optional[float]:
            try:
                if hasattr(self.model, "weights"):
                    # VotingRegressor accepts plain list weights
                    self.model.weights = list(w_tuple)
                preds = self.model.predict(X_val)
                return float(mean_absolute_error(y_val, preds))
            except Exception:
                return None

        # If Optuna is available, use it for continuous optimization
        try:
            import optuna  # type: ignore
            _OPTUNA_AVAILABLE = True
        except Exception:
            _OPTUNA_AVAILABLE = False

        # If candidate_weights provided and Optuna not available, evaluate candidates
        if not _OPTUNA_AVAILABLE:
            if candidate_weights is None:
                candidate_weights = [
                    (0.4, 0.4, 0.2),
                    (0.33, 0.33, 0.34),
                    (0.5, 0.25, 0.25),
                    (0.2, 0.6, 0.2),
                    (0.2, 0.2, 0.6),
                ]

            # If xgboost not available, drop the middle weight from candidates
            if not _XGB_AVAILABLE:
                candidate_weights = [tuple([w for i, w in enumerate(c) if i != 1]) for c in candidate_weights]

            best_mae = None
            best_w = tuple(getattr(self, "weights", ()))

            for cand in candidate_weights:
                total = float(sum(cand))
                if total <= 0:
                    continue
                w = tuple([float(v) / total for v in cand])
                mae = _eval_weights(w)
                if mae is None:
                    continue
                if best_mae is None or mae < best_mae:
                    best_mae = mae
                    best_w = w

            # Persist best weights
            try:
                self.weights = tuple(best_w)
                if hasattr(self.model, "weights"):
                    self.model.weights = list(best_w)
            except Exception:
                pass

            return best_mae, tuple(best_w)

        # Optuna-based tuning path
        def _normalize(arr: np.ndarray) -> Tuple[float, ...]:
            s = float(np.sum(arr))
            if s <= 0:
                arr = np.ones_like(arr, dtype=float)
                s = float(np.sum(arr))
            return tuple((arr / s).tolist())

        # Build and run an Optuna study minimizing MAE
        def _objective(trial: "optuna.trial.Trial") -> float:
            if _XGB_AVAILABLE:
                a = trial.suggest_float("a", 0.0, 1.0)
                b = trial.suggest_float("b", 0.0, 1.0)
                c = trial.suggest_float("c", 0.0, 1.0)
                vec = np.array([a, b, c], dtype=float)
            else:
                a = trial.suggest_float("a", 0.0, 1.0)
                b = trial.suggest_float("b", 0.0, 1.0)
                vec = np.array([a, b], dtype=float)

            w = _normalize(vec)
            mae = _eval_weights(w)
            # If evaluation failed, return a large penalty
            if mae is None:
                return 1e6
            return mae

        study = optuna.create_study(direction="minimize")
        study.optimize(_objective, n_trials=n_trials, timeout=timeout)

        # Compose best weights
        best_params = study.best_params
        if _XGB_AVAILABLE:
            arr = np.array([best_params.get("a", 0.0), best_params.get("b", 0.0), best_params.get("c", 0.0)], dtype=float)
        else:
            arr = np.array([best_params.get("a", 0.0), best_params.get("b", 0.0)], dtype=float)

        best_w = _normalize(arr)
        best_mae = _eval_weights(best_w)

        # Persist best weights
        try:
            self.weights = tuple(best_w)
            if hasattr(self.model, "weights"):
                self.model.weights = list(best_w)
        except Exception:
            pass

        return best_mae, tuple(best_w)

    def save(self, path: str):
        """Persist the ensemble to `path` (file path).

        The directory containing `path` will be created if necessary.
        """
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str) -> "EnsembleModel":
        obj = joblib.load(path)
        if not isinstance(obj, EnsembleModel):
            raise ValueError(f"Loaded object is not EnsembleModel: {type(obj)}")
        return obj


__all__ = ["EnsembleModel"]
