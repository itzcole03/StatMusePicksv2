"""Run a small training smoke job that generates a tiny dataset and invokes train_from_dataset.

This script is designed to be fast and deterministic for CI smoke runs.
"""
from pathlib import Path

import pandas as pd

from backend.training.train_models import train_from_dataset


def make_small_dataset(path: Path):
    rows = []
    for pid in (1, 2):
        for i in range(8):
            split = "train" if i < 5 else ("val" if i == 5 else "test")
            rows.append(
                {
                    "player_id": pid,
                    "player_name": f"Player {pid}",
                    "game_date": f"2025-01-{10 + i}",
                    "target": float(pid * 10 + i),
                    # include a simple numeric feature so sklearn trains
                    "feature_1": float(i),
                    "split": split,
                }
            )
    df = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def main():
    out = Path("./tmp_training_smoke")
    out.mkdir(exist_ok=True)
    dataset = out / "smoke_dataset.csv"
    make_small_dataset(dataset)
    models_store = out / "models_store"
    print("Running training smoke on:", dataset)
    results = train_from_dataset(str(dataset), str(models_store), min_games=3)
    print("Training smoke results:\n", results)


if __name__ == "__main__":
    main()
