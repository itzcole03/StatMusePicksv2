import os
import joblib

from backend.services.test_models import DummyModel


def main():
    model_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models_store")
    os.makedirs(model_dir, exist_ok=True)
    path = os.path.join(model_dir, "LeBron_James.pkl")
    joblib.dump(DummyModel(), path)
    print("Wrote test model to", path)


if __name__ == '__main__':
    main()
