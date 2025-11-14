import os
import tempfile
from pathlib import Path

import joblib
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.model_registry import PlayerModelRegistry
from sklearn.dummy import DummyRegressor


def test_admin_promote_endpoint():
    # Set admin key env var
    os.environ["ADMIN_API_KEY"] = "testkey"
    with tempfile.TemporaryDirectory() as td:
        store = Path(td) / "models_store"
        store.mkdir(parents=True, exist_ok=True)
        # create a test model using the registry at that store
        reg = PlayerModelRegistry(str(store))
        m = DummyRegressor(strategy="constant", constant=2.0)
        m.fit([[0]], [2.0])
        version = reg.save_model("Admin Player", m, metadata={"notes": "test"})

        # override MODEL_STORE_DIR env so the endpoint uses the same store
        os.environ["MODEL_STORE_DIR"] = str(store)

        client = TestClient(app)
        resp = client.post(
            "/api/admin/promote",
            headers={"X-ADMIN-KEY": "testkey"},
            json={"player": "Admin Player", "version": version, "promoted_by": "ci", "notes": "promote test", "write_legacy": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        meta = data.get("metadata")
        assert meta is not None
        assert meta.get("promoted") is True
        # check legacy pkl exists
        legacy = store / "Admin_Player.pkl"
        assert legacy.exists()
        loaded = joblib.load(legacy)
        assert hasattr(loaded, "predict")
