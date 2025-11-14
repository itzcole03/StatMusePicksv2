import json
from pathlib import Path
import pandas as pd

from backend.training.train_models import train_from_dataset


def _make_dataset(path: Path):
    # two players, one single-class (Alice), one mixed (Bob)
    rows = []
    # Alice (player_id=1) all zeros
    for i in range(6):
        rows.append({"player_id": 1, "player_name": "Alice", "f1": float(i), "f2": float(i * 2), "target": 0})
    # Bob (player_id=2) mixed 0/1
    for i in range(6):
        rows.append({"player_id": 2, "player_name": "Bob", "f1": float(i), "f2": float(i * 3), "target": (i % 2)})
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def test_single_class_skipped(tmp_path):
    ds = tmp_path / "sample_dataset.csv"
    _make_dataset(ds)
    store = tmp_path / "models_store"
    report = tmp_path / "report.csv"

    res = train_from_dataset(str(ds), store_dir=str(store), min_games=3, trials=3, report_csv=str(report))

    # summary file should exist
    summary_path = store / f"training_summary_{ds.stem}.json"
    assert summary_path.exists(), "summary json not written"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    # Alice (single-class) should have an entry and empty metrics (baseline/fallback)
    assert "Alice" in summary
    assert isinstance(summary["Alice"].get("metrics"), dict)

    # Bob should have metrics (classification path)
    assert "Bob" in summary
    bob_metrics = summary["Bob"].get("metrics", {})
    # at least presence of brier key (may be None if not enough holdout), but should be a dict
    assert isinstance(bob_metrics, dict)


def test_objective_returns_finite(tmp_path):
    ds = tmp_path / "sample_dataset2.csv"
    _make_dataset(ds)
    store = tmp_path / "models_store2"

    res = train_from_dataset(str(ds), store_dir=str(store), min_games=3, trials=3, report_csv=None)

    # Inspect Bob metrics to ensure brier (if present) is finite and not inf
    summary_path = store / f"training_summary_{ds.stem}.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    bob = summary.get("Bob")
    assert bob is not None
    metrics = bob.get("metrics", {})
    # if a brier value exists it must be finite between 0 and 1
    brier = metrics.get("brier")
    if brier is not None:
        assert isinstance(brier, (int, float))
        assert brier >= 0.0 and brier <= 1.0

    # Also assert that registry index and artifact files exist
    idx_path = Path(store) / "index.json"
    assert idx_path.exists(), "registry index.json missing"
    idx = json.loads(idx_path.read_text(encoding="utf-8"))
    # index entries should include at least one entry whose metadata.player_name == Alice or Bob
    found_names = {entry.get("player_name") for entries in idx.values() for entry in entries}
    assert "Alice" in found_names or "Bob" in found_names
    # Ensure that at least one joblib artifact file exists in the store
    joblibs = list(Path(store).glob("*.joblib"))
    assert len(joblibs) >= 1, "no joblib artifacts written"


def test_registry_loads_model(tmp_path):
    ds = tmp_path / "sample_dataset3.csv"
    _make_dataset(ds)
    store = tmp_path / "models_store3"

    _ = train_from_dataset(str(ds), store_dir=str(store), min_games=3, trials=3, report_csv=None)

    # Use registry to list and load models
    from backend.services.model_registry import PlayerModelRegistry

    reg = PlayerModelRegistry(str(store))
    # Ensure index.json exists and versions listed
    idx = reg.list_models()
    assert isinstance(idx, dict)
    # At least one of the players should have a saved version
    found = False
    for safe, entries in idx.items():
        if entries:
            found = True
            # load latest
            ver = entries[-1]["version"]
            name = entries[-1]["player_name"]
            model = reg.load_model(name, version=ver)
            assert model is not None
    assert found, "No saved model entries found in registry"


def test_degenerate_folds_fallback(tmp_path):
    # Create a dataset where Alice is single-class; force folds with empty val to exercise optuna-degenerate path
    ds = tmp_path / "sample_dataset4.csv"
    _make_dataset(ds)
    store = tmp_path / "models_store4"

    import backend.training.train_models as tm
    orig_split = tm.time_series_cv_split
    try:
        # Make folds exist but with empty val/test so objectives see no validation rows
        def fake_split(group, n_splits=3, val_size=0.15, test_size=0.15):
            return [{"train": group, "val": pd.DataFrame(), "test": pd.DataFrame()}]

        tm.time_series_cv_split = fake_split
        res = tm.train_from_dataset(str(ds), store_dir=str(store), min_games=3, trials=2, report_csv=None)
        # Alice should be present and either baseline or have a model; ensure registry index written
        idxp = Path(store) / "index.json"
        assert idxp.exists()
        idx = json.loads(idxp.read_text(encoding="utf-8"))
        # find Alice or Bob
        names = {e.get("player_name") for entries in idx.values() for e in entries}
        assert "Alice" in names or "Bob" in names
    finally:
        tm.time_series_cv_split = orig_split
