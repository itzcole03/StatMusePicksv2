"""Persist a toy model and register it in the local Model Registry.

This script is safe for local dev. It will:
 - train a tiny DummyRegressor if scikit-learn is available
 - otherwise persist a small Python dict as a stub model
 - save the artifact to `./backend/models_store/tmp_toy_model.*`
 - register the artifact with `backend.services.simple_model_registry.ModelRegistry`

Run:
  & .venv\Scripts\Activate.ps1
  python backend/scripts/persist_toy_model.py
"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "backend" / "models_store" / "toy_models"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def save_with_joblib(obj, path: Path):
    try:
        import joblib

        joblib.dump(obj, path)
        return True
    except Exception:
        # fallback to pickle
        import pickle

        with open(path, "wb") as fh:
            pickle.dump(obj, fh)
        return True


def build_and_persist():
    # try to build a tiny sklearn model
    model = None
    model_type = "dict_stub"
    try:
        from sklearn.dummy import DummyRegressor
        import numpy as _np

        X = _np.arange(100).reshape(-1, 1)
        y = (_np.arange(100) % 2).astype(float)
        m = DummyRegressor(strategy="constant", constant=0.5)
        m.fit(X, y)
        model = m
        model_type = "sklearn.DummyRegressor"
    except Exception:
        # fallback: simple serializable dict
        model = {"mean": 0.5, "notes": "fallback stub model"}

    artifact_path = OUT_DIR / "toy_model_1.joblib"
    save_with_joblib(model, artifact_path)

    # register in the simple registry
    try:
        from backend.services.simple_model_registry import ModelRegistry

        reg = ModelRegistry()
        meta = reg.register_model("toy-points-model", artifact_src=artifact_path, metadata={"model_type": model_type, "source": "persist_toy_model.py"})
        print(json.dumps({"registered": True, "version_id": meta.version_id, "artifact": meta.artifact_path}, indent=2))
    except Exception as e:
        print("Failed to register model in registry:", e, file=sys.stderr)
        print(json.dumps({"registered": False, "artifact": str(artifact_path)}))


if __name__ == "__main__":
    build_and_persist()
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

