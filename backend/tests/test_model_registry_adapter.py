import json
from pathlib import Path

import pytest

from backend.services.model_registry import PlayerModelRegistry


def test_save_model_registers_to_per_version_registry(monkeypatch, tmp_path):
    recorded = {}

    class DummyPerReg:
        def __init__(self, base_path=None):
            pass

        def register_model(self, name, artifact_src=None, metadata=None):
            recorded["name"] = name
            recorded["artifact_src"] = str(artifact_src)
            recorded["metadata"] = metadata
            # return a lightweight object mimicking simple_model_registry.ModelMetadata
            return None

    # Patch the PerVersionRegistry used in the model_registry module
    monkeypatch.setattr("backend.services.model_registry.PerVersionRegistry", DummyPerReg)

    # Create a legacy registry pointing at a temp backend models_store
    store_dir = tmp_path / "backend_models_store"
    reg = PlayerModelRegistry(store_dir=str(store_dir))

    dummy_model = {"x": 1}
    version = reg.save_model("Test Player", dummy_model, metadata={"model_type": "dummy"})

    assert version is not None
    # adapter should have been called with safe name
    assert recorded.get("name") == "Test_Player"
    assert "artifact_src" in recorded
    assert recorded["metadata"].get("model_type") == "dummy"
