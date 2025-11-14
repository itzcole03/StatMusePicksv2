import asyncio
import tempfile
import os
from pathlib import Path
import pandas as pd

import pytest

from backend.services import training_data_service as tds


def _make_synthetic_rows(num_players=10, games_per_player=60, stat_type="points"):
    rows = []
    # Create dates from 2020-01-01 onwards (oldest first). We will reverse later if needed.
    for pid in range(1, num_players + 1):
        for i in range(games_per_player):
            day = i + 1
            rows.append(
                {
                    "player_id": pid,
                    "player_name": f"Player {pid}",
                    "player_team": f"TEAM{pid}",
                    "player_position": "G",
                    "game_id": pid * 1000 + i,
                    "game_date": f"2020-01-{(day%28)+1:02d}",
                    "home_team": "HT",
                    "away_team": "AT",
                    "stat_type": stat_type,
                    "stat_value": float(10 + (i % 30)),
                }
            )
    # The DB fetcher expects rows in arbitrary order; training pipeline sorts per player
    return rows


def test_generate_and_save_dataset_with_synthetic(monkeypatch, tmp_path):
    rows = _make_synthetic_rows(num_players=10, games_per_player=60, stat_type="points")

    async def _fake_fetch(stat_type, player_ids=None):
        # ignore args and return the synthetic rows
        return rows

    # Patch the async DB fetcher
    monkeypatch.setattr(tds, "fetch_player_stat_rows", _fake_fetch)

    # Run the end-to-end generator
    out_dir = str(tmp_path / "out")
    meta = asyncio.run(tds.generate_and_save_dataset(stat_type="points", player_ids=None, out_dir=out_dir, min_games_per_player=50))

    assert "path" in meta
    saved_path = Path(meta["path"])
    assert saved_path.exists()

    # Load the saved dataset (Parquet or CSV)
    if saved_path.suffix == ".parquet":
        df = pd.read_parquet(saved_path)
    else:
        df = pd.read_csv(saved_path)

    # Check distinct players and per-player counts
    players = df["player_id"].unique().tolist()
    assert len(players) == 10
    counts = df.groupby("player_id").size()
    for c in counts:
        assert c >= 50

    # Verify no leakage: ensure per-player train/val/test slices are chronological
    # The pipeline assigns a `split` column
    assert "split" in df.columns
    for pid in players:
        g = df[df["player_id"] == pid].copy()
        g["game_date"] = pd.to_datetime(g["game_date"])
        train = g[g["split"] == "train"]
        val = g[g["split"] == "val"]
        test = g[g["split"] == "test"]
        if not val.empty and not test.empty and not train.empty:
            # allow equal-date boundaries (no leakage means no overlapping game_ids)
            assert train["game_date"].max() <= val["game_date"].min()
            assert val["game_date"].max() <= test["game_date"].min()
            # ensure splits are disjoint by game id
            ids_train = set(train["game_id"].tolist())
            ids_val = set(val["game_id"].tolist())
            ids_test = set(test["game_id"].tolist())
            assert ids_train.isdisjoint(ids_val)
            assert ids_val.isdisjoint(ids_test)
            assert ids_train.isdisjoint(ids_test)
