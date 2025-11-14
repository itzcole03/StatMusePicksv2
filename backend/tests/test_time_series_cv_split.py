import pandas as pd
from pathlib import Path

from backend.services.training_data_service import time_series_cv_split


def test_time_series_cv_basic():
    # build synthetic player with 12 games
    rows = []
    for i in range(12):
        rows.append({
            "player_id": 1,
            "player_name": "Player 1",
            "game_date": f"2025-01-{10 + i}",
            "target": float(i),
        })
    df = pd.DataFrame(rows)

    folds = time_series_cv_split(df, n_splits=3, val_size=0.1, test_size=0.1)
    assert len(folds) == 3

    # Ensure chronological ordering in each fold
    for f in folds:
        tr = f["train"].sort_values("game_date")
        vl = f["val"].sort_values("game_date")
        te = f["test"].sort_values("game_date")
        if not vl.empty and not tr.empty:
            assert tr["game_date"].max() < vl["game_date"].min()
        if not te.empty and not vl.empty:
            assert vl["game_date"].max() < te["game_date"].min()

    # Union of fold parts should be subset of original rows (compare by player_id+game_date)
    union_rows = pd.concat([pd.concat([f["train"], f["val"], f["test"]]) for f in folds], ignore_index=True)
    union_unique = union_rows.drop_duplicates(subset=["player_id", "game_date"])
    orig_set = set((r["player_id"], pd.to_datetime(r["game_date"])) for _, r in df.iterrows())
    union_set = set((r["player_id"], pd.to_datetime(r["game_date"])) for _, r in union_unique.iterrows())
    assert union_set.issubset(orig_set)
