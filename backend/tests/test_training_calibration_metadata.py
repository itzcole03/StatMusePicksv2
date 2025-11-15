import json
from pathlib import Path

import numpy as np
import pandas as pd

from backend.training.train_models import train_from_dataset


def _make_sample_classification_dataset(tmp_path: Path) -> Path:
    # Create a tiny per-player dataset with train/val/test splits
    rows = []
    # player 1: 80 rows
    for i in range(80):
        split = "train" if i < 56 else ("val" if i < 68 else "test")
        # simple feature correlated with target
        feat = float(i) / 80.0
        target = 1 if feat > 0.5 else 0
        rows.append({"player_id": "p1", "player_name": "Test Player", "game_date": f"2025-01-{i%30+1:02d}", "feature1": feat, "target": target, "split": split})

    df = pd.DataFrame(rows)
    path = tmp_path / "sample_classification.parquet"
    df.to_parquet(path)
    return path


def test_training_persists_calibration_metadata(tmp_path):
    dataset = _make_sample_classification_dataset(tmp_path)
    store_dir = str(tmp_path / "models_store")

    res = train_from_dataset(str(dataset), store_dir=store_dir, min_games=10, trials=2)
    # results keyed by player_name
    assert isinstance(res, dict)
    assert "Test Player" in res
    version = res["Test Player"]["version"]
    # read saved metadata from the store index (PlayerModelRegistry uses index.json)
    index_path = Path(store_dir) / "index.json"
    assert index_path.exists(), f"expected registry index at {index_path}"
    idx = json.loads(index_path.read_text(encoding="utf-8"))
    # PlayerModelRegistry uses a safe name (spaces -> underscores) as the index key
    safe = "Test_Player"
    entries = idx.get(safe)
    assert entries is not None and len(entries) > 0, f"no index entries for {safe}"
    # Use the latest entry
    entry = entries[-1]
    # The registry stores the calibration summary at the top-level of the entry
    # (see ModelMetadata.calibration). Accept None when calibrator couldn't be fit.
    assert "calibration" in entry, "Expected 'calibration' key in saved index entry"
    calib = entry.get("calibration")
    if calib is not None:
        assert "raw" in calib and "calibrated" in calib and "calibrator_version" in calib
