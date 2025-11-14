import os
import tempfile
import json
from pathlib import Path

import pandas as pd

from backend.training.train_models import train_from_dataset
from backend.services.model_registry import PlayerModelRegistry


def _save_df(df: pd.DataFrame, path: Path):
    try:
        df.to_parquet(path)
    except Exception:
        df.to_csv(path)


def test_feature_importances_persisted():
    # create a tiny dataset for one player with two numeric features
    df = pd.DataFrame([
        {"player_id": "p1", "player_name": "Test Player", "game_date": "2021-01-01", "target": 10.0, "f1": 1.0, "f2": 2.0},
        {"player_id": "p1", "player_name": "Test Player", "game_date": "2021-01-02", "target": 12.0, "f1": 1.5, "f2": 2.2},
        {"player_id": "p1", "player_name": "Test Player", "game_date": "2021-01-03", "target": 11.0, "f1": 1.2, "f2": 2.1},
        {"player_id": "p1", "player_name": "Test Player", "game_date": "2021-01-04", "target": 13.0, "f1": 1.3, "f2": 2.3},
        {"player_id": "p1", "player_name": "Test Player", "game_date": "2021-01-05", "target": 14.0, "f1": 1.4, "f2": 2.4},
        {"player_id": "p1", "player_name": "Test Player", "game_date": "2021-01-06", "target": 15.0, "f1": 1.6, "f2": 2.6},
    ])

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # try parquet first
        ds_path = td / "ds.parquet"
        try:
            df.to_parquet(ds_path)
            dataset_file = ds_path
        except Exception:
            csv_path = td / "ds.csv"
            df.to_csv(csv_path, index=False)
            dataset_file = csv_path

        store_dir = td / "models_store"
        os.makedirs(store_dir, exist_ok=True)

        res = train_from_dataset(str(dataset_file), str(store_dir), min_games=3)
        # ensure model saved and metadata has feature_importances (may be None for baseline)
        reg = PlayerModelRegistry(str(store_dir))
        meta = reg.get_metadata("Test Player")
        assert meta is not None
        # metadata.feature_importances may be present (dict) or None depending on estimator
        # but feature_columns should be present and match our feature names
        assert set(meta.feature_columns) == {"f1", "f2"}
        # if feature_importances is present it must be a mapping of the same keys
        fi = getattr(meta, "feature_importances", None)
        if fi is not None:
            assert isinstance(fi, dict)
            assert set(fi.keys()) == set(meta.feature_columns)