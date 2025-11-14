import json
from pathlib import Path

import pandas as pd

from backend.training.train_models import train_from_dataset
from backend.services.model_registry import PlayerModelRegistry


def test_train_from_small_dataset(tmp_path):
    # create synthetic dataset CSV with two players and train/val/test splits
    rows = []
    for pid in (1, 2):
        for i in range(6):
            split = "train" if i < 4 else ("val" if i == 4 else "test")
            rows.append({
                "player_id": pid,
                "player_name": f"Player {pid}",
                "game_date": f"2025-01-{10 + i}",
                "target": float(pid * 10 + i),
                "split": split,
            })

    df = pd.DataFrame(rows)
    dataset_path = tmp_path / "small_dataset.csv"
    df.to_csv(dataset_path, index=False)

    store = tmp_path / "models_store"
    res = train_from_dataset(str(dataset_path), str(store), min_games=3)
    # Ensure both players are present in results
    assert "Player 1" in res and "Player 2" in res

    # confirm registry contains models
    reg = PlayerModelRegistry(str(store))
    v1 = reg.list_versions("Player 1")
    assert len(v1) == 1
    meta = reg.get_metadata("Player 1")
    assert meta is not None
    # model_type should be present and reflect the trained model (baseline or sklearn)
    assert getattr(meta, "model_type", None) is not None
