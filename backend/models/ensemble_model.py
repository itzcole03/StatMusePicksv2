"""Compatibility shim for legacy pickled ensemble models.

Some saved model artifacts reference `backend.models.ensemble_model` during
unpickling. This module provides lightweight fallback classes with a safe
`predict` method so artifacts can be loaded for inspection or warmed into
the registry. These fallbacks are intentionally conservative and return
deterministic outputs when the original estimator logic is not present.
"""
from __future__ import annotations
import numpy as np


class _PredictFallback:
    def predict(self, X):
        try:
            arr = np.asarray(X)
            if arr.ndim == 1:
                arr = arr.reshape(1, -1)
            n = arr.shape[0]
            # Prefer any exposed scalar summary attributes if available
            for attr in ('season_avg', 'seasonAvg', 'mean_', 'baseline'):
                if hasattr(self, attr):
                    try:
                        return np.full((n,), float(getattr(self, attr)))
                    except Exception:
                        pass
            # Fallback: average across features as a weak proxy
            try:
                vals = arr.mean(axis=1)
                return vals
            except Exception:
                return np.zeros(n)
        except Exception:
            return np.zeros(1)


class EnsembleModel(_PredictFallback):
    """Legacy ensemble placeholder."""
    pass


class StackedModel(_PredictFallback):
    """Legacy stacked model placeholder."""
    pass


class CustomEnsemble(_PredictFallback):
    """Custom ensemble placeholder used in older training code."""
    pass


class EnsembleWrapper(_PredictFallback):
    """Wrapper placeholder that previously delegated to inner estimators."""
    pass


# Module-level __all__ for clarity
__all__ = [
    'EnsembleModel',
    'StackedModel',
    'CustomEnsemble',
    'EnsembleWrapper',
]
