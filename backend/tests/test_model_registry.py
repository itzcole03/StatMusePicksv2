import json
from pathlib import Path

import pytest

from backend.services.simple_model_registry import ModelRegistry


def test_register_and_get_model(tmp_path):
    registry_base = tmp_path / "models_store"
    registry = ModelRegistry(base_path=registry_base)

    # create a dummy artifact file
    artifact = tmp_path / "dummy_model.bin"
    artifact.write_text("model-bytes")

    meta = registry.register_model(name="test-model", artifact_src=artifact, metadata={"framework": "pytorch", "score": 0.9})

    assert meta.name == "test-model"
    assert len(meta.version_id) > 0
    assert meta.artifact_path != ""

    # check that artifact was copied into the registry
    artifact_dest = Path(meta.artifact_path)
    assert artifact_dest.exists()
    assert artifact_dest.read_text() == "model-bytes"

    # list models and versions
    models = registry.list_models()
    assert "test-model" in models

    versions = registry.list_versions("test-model")
    assert meta.version_id in versions

    # get latest
    latest = registry.latest_model("test-model")
    assert latest is not None
    assert latest.version_id == meta.version_id

