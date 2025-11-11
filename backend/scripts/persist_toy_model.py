import os
import json

from sklearn.ensemble import RandomForestRegressor
import numpy as np

from backend.services.model_registry import ModelRegistry


def main():
    # Simple synthetic dataset: predict target = linear function + noise
    rng = np.random.RandomState(42)
    X = rng.randn(200, 5)
    coef = np.array([0.5, -0.2, 0.3, 0.0, 0.1])
    y = X.dot(coef) + rng.normal(scale=0.5, size=X.shape[0])

    model = RandomForestRegressor(n_estimators=50, random_state=42)
    model.fit(X, y)

    registry = ModelRegistry()
    player_name = os.environ.get('TOY_PLAYER_NAME', 'LeBron James')
    version = 'v0.1'
    notes = 'Toy RandomForest model trained on synthetic data - for testing ModelRegistry'

    registry.save_model(player_name, model, version=version, notes=notes)

    # Report: check file existence
    path = registry._model_path(player_name)
    out = {
        'saved_for': player_name,
        'version': version,
        'notes': notes,
        'path': os.path.abspath(path),
        'exists_on_disk': os.path.exists(path),
    }
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
