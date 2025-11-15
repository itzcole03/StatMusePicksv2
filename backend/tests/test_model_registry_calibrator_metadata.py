import joblib
from backend.services.model_registry import PlayerModelRegistry


def test_save_model_persists_calibrator_version(tmp_path):
    store = tmp_path / "models_store"
    store.mkdir()
    reg = PlayerModelRegistry(str(store))

    player = "Meta Player"
    dummy = {"mean": 10.0}
    meta = {"model_type": "mean_baseline", "calibrator_version": "cal-12345"}

    version = reg.save_model(player, dummy, metadata=meta)

    # retrieve metadata via registry
    m = reg.get_metadata(player, version=version)
    assert m is not None
    assert getattr(m, "calibrator_version", None) == "cal-12345"
