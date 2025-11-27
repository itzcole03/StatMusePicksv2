import json
import os

from backend.services.model_registry import ModelRegistry


class DummyModel:
    def __init__(self):
        self._kept_contextual_features = ["feat_a", "feat_b"]
        self._feature_list = ["feat_a", "feat_b", "feat_c"]

    def predict(self, X):
        return [0] * len(X)


def test_model_feature_list_sidecar(tmp_path):
    m = DummyModel()
    outdir = tmp_path / "models"
    reg = ModelRegistry(model_dir=str(outdir))
    reg.save_model("Dummy Player", m, version="v1", notes="unit-test")

    # sidecar should be written next to the model file
    model_path = reg._model_path("Dummy Player")
    sidecar = os.path.splitext(model_path)[0] + "_metadata.json"
    assert os.path.exists(sidecar)
    with open(sidecar, "r", encoding="utf8") as fh:
        data = json.load(fh)
    assert data.get("name") == "Dummy Player"
    assert "kept_contextual_features" in data
    assert data.get("feature_list") == ["feat_a", "feat_b", "feat_c"]

    # Model file should exist
    assert os.path.exists(model_path)
