import tempfile
import os
from pathlib import Path

import joblib
from sklearn.dummy import DummyRegressor

from backend.services.model_registry import PlayerModelRegistry


def test_promote_model_writes_metadata_and_legacy_pkl():
    with tempfile.TemporaryDirectory() as td:
        store = Path(td) / "models_store"
        store.mkdir(parents=True, exist_ok=True)

        reg = PlayerModelRegistry(str(store))
        # save a tiny dummy model
        m = DummyRegressor(strategy="constant", constant=1.0)
        m.fit([[0]], [1.0])
        version = reg.save_model("Promo Player", m, metadata={"notes": "test"})

        # promote and write legacy pkl
        meta = reg.promote_model("Promo Player", version=version, promoted_by="tester", notes="promote test", write_legacy_pkl=True)
        assert meta is not None
        assert meta.get("promoted") is True
        assert meta.get("promoted_by") == "tester"
        # check legacy pkl exists
        legacy = store / "Promo_Player.pkl"
        assert legacy.exists()
        # loaded model should be usable
        loaded = joblib.load(legacy)
        assert hasattr(loaded, "predict")
