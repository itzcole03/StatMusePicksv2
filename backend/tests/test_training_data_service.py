import tempfile
import os
import shutil
import pandas as pd

from backend.services.training_data_service import (
    generate_samples_from_game_history,
    time_based_split,
    save_dataset,
)


def make_games(n=6):
    # newest-first: most recent at index 0
    base = 20
    games = []
    for i in range(n):
        # dates descending from 2025-01-06 backwards
        day = 6 - i
        games.append({"statValue": float(base - 2 * i), "date": f"2025-01-{day:02d}"})
    return games


def test_generate_samples_basic():
    games = make_games(6)
    df = generate_samples_from_game_history("Test Player", games, lookback=3, min_lookback=1)
    # Expect samples for all games except the oldest which has no prior games
    assert not df.empty
    assert len(df) == 5
    # The first sample corresponds to games[0] (most recent)
    first_target = df.iloc[0]["target"]
    assert first_target == games[0]["statValue"]


def test_time_based_split_and_save(tmp_path):
    games = make_games(6)
    df = generate_samples_from_game_history("Test Player", games, lookback=3, min_lookback=1)
    train, val, test = time_based_split(df, date_col="game_date", train_pct=0.6, val_pct=0.2)
    # With 5 samples: train=3, val=1, test=1
    assert len(train) == 3
    assert len(val) == 1
    assert len(test) == 1

    out_dir = tmp_path / "out"
    meta = save_dataset(train, str(out_dir), "test_dataset")
    assert os.path.exists(meta["parquet"]) is True
    assert os.path.exists(meta["meta"]) is True
    # metadata rows should match
    assert meta["meta_obj"]["rows"] == len(train)
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from backend.services import training_data_service as tds


def make_sample_rows(player_id=1, n=10, stat_type="points", start=None):
    if start is None:
        start = datetime(2025, 11, 13, 0, 0)
    rows = []
    for i in range(n):
        gd = start - timedelta(days=2 * i)
        rows.append(
            {
                "player_id": player_id,
                "player_name": f"Player {player_id}",
                "player_team": "TST",
                "player_position": None,
                "game_id": i + 1,
                "game_date": gd.isoformat(),
                "home_team": "TST",
                "away_team": f"OPP{i}",
                "stat_type": stat_type,
                "stat_value": float(20 + i),
            }
        )
    return rows


def test_make_time_splits():
    rows = make_sample_rows(n=10)
    df = pd.DataFrame(rows)
    out = tds.make_time_splits(df)
    # Expect train=7, val=1, test=2 (based on 70/15/15 rounding in implementation)
    counts = out["split"].value_counts().to_dict()
    assert counts.get("train", 0) == 7
    assert counts.get("val", 0) == 1
    assert counts.get("test", 0) == 2


def async_return(val):
    async def _inner(*args, **kwargs):
        return val

    return _inner


def test_generate_and_save_dataset(tmp_path, monkeypatch):
    # Create sample rows for two players
    rows_p1 = make_sample_rows(player_id=1, n=8)
    rows_p2 = make_sample_rows(player_id=2, n=6)
    all_rows = rows_p1 + rows_p2

    # Monkeypatch the DB fetcher to return our sample rows
    monkeypatch.setattr(tds, "fetch_player_stat_rows", async_return(all_rows))

    out_dir = tmp_path / "datasets"

    # Run the generator with a low min_games so both players included
    meta = asyncio.run(
        tds.generate_and_save_dataset(
            stat_type="points", player_ids=None, out_dir=str(out_dir), min_games_per_player=5
        )
    )

    # Metadata should be returned and file must exist
    assert "version_id" in meta
    path = Path(meta["path"])
    assert path.exists()

    # Load the saved CSV/parquet and verify basic schema
    if path.suffix == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_parquet(path)

    assert "player_id" in df.columns
    assert "target" in df.columns
    # check that only players with >=5 games were kept
    kept_players = set(df["player_id"].unique())
    assert 1 in kept_players
    assert 2 in kept_players
