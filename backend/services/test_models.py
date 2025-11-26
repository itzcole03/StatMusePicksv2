class DummyModel:
    """A tiny model class used only for tests; kept in an importable module
    so joblib pickles/unpickles correctly during pytest runs.
    """

    def predict(self, X):
        try:
            return [0 for _ in range(len(X))]
        except Exception:
            return [0]
