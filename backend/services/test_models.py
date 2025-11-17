class DummyModel:
    """A tiny model class used only for tests; kept in an importable module
    so joblib pickles/unpickles correctly during pytest runs.
    """
    def predict(self, X):
        try:
            return [0 for _ in range(len(X))]
        except Exception:
            return [0]


class PersistedDummy:
    """A small deterministic model used to create persisted artifacts for tests.

    The `predict` method returns a numpy array of shape (n_samples,) filled
    with the configured value so integration tests can assert exact outputs.
    """
    def __init__(self, v: float = 42.0):
        self.v = float(v)

    def predict(self, X):
        import numpy as _np

        n = 1
        try:
            n = int(len(X))
        except Exception:
            n = 1
        return _np.array([float(self.v) for _ in range(n)])
