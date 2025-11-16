import os
import joblib
import numpy as np


class PersistedDummy:
    def __init__(self, value=42.0, n_features=34):
        self._value = float(value)
        self.n_features_in_ = int(n_features)

    def predict(self, X):
        # Return numpy array shaped (n_samples,)
        try:
            n = len(X)
        except Exception:
            n = 1
        return np.array([self._value for _ in range(n)])


def main():
    repo_root = os.path.dirname(os.path.dirname(__file__))
    model_dir = os.path.join(repo_root, 'backend', 'models_store')
    os.makedirs(model_dir, exist_ok=True)
    path = os.path.join(model_dir, 'LeBron_James.pkl')
    joblib.dump(PersistedDummy(), path)
    print('Wrote persisted dummy model to', path)


if __name__ == '__main__':
    main()
