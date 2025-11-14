import numpy as np

class DummyModel:
    """Simple deterministic model used for integration tests.

    It expects a pandas.DataFrame with column `last5` and returns
    1.1 * last5 as the predicted raw value.
    """
    def predict(self, X):
        try:
            return np.array([float(X['last5'].iloc[0]) * 1.1])
        except Exception:
            return np.array([0.0])
