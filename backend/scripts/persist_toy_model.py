import os
import joblib

def main():
    """Persist a small sklearn DummyRegressor so tests can load a real model artifact."""
    player = os.environ.get("TOY_PLAYER_NAME", "LeBron James")
    safe = player.replace(" ", "_")
    model_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models_store'))
    os.makedirs(model_dir, exist_ok=True)
    path = os.path.join(model_dir, f"{safe}.pkl")

    try:
        from sklearn.dummy import DummyRegressor
        import numpy as np

        model = DummyRegressor(strategy='mean')
        # Fit on trivial data so predict works
        X = np.zeros((5, 1))
        y = np.zeros(5)
        model.fit(X, y)
    except Exception:
        # Fallback: store a simple dict so load succeeds
        model = {"stub": True}

    joblib.dump(model, path)
    print(f"Wrote toy model to {path}")


if __name__ == '__main__':
    main()

