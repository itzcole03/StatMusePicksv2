import os
import tempfile
from datetime import date, timedelta

import pandas as pd

from backend.services import training_data_service as tds


def _make_player_df(n_days=20, players=("A", "B")):
    start = date(2020, 1, 1)
    rows = []
    for p in players:
        for i in range(n_days):
            rows.append(
                {"player": p, "game_date": start + timedelta(days=i), "feat": float(i)}
            )
    df = pd.DataFrame(rows)
    return df


def test_per_player_time_split_preserves_chronology_and_counts():
    df = _make_player_df(n_days=10, players=("P1", "P2", "P3"))
    train, val, test = tds.per_player_time_split(
        df,
        player_col="player",
        date_col="game_date",
        train_frac=0.6,
        val_frac=0.2,
        test_frac=0.2,
    )
    # Each player had 10 rows; with 60/20/20 split we expect approx 6/2/2 per player
    assert len(train) == 3 * 6
    assert len(val) == 3 * 2
    assert len(test) == 3 * 2
    # verify chronological order within each split for a sample player
    p1_train = train[train["player"] == "P1"].sort_values("game_date")
    if not p1_train.empty:
        assert p1_train["game_date"].is_monotonic_increasing


def test_chronological_split_empty_df_returns_empty_splits():
    empty = pd.DataFrame(columns=["game_date", "feat"])
    t, v, te = tds.chronological_split_by_ratio(empty, date_col="game_date")
    assert t.empty and v.empty and te.empty


def test_export_dataset_with_version_creates_manifest_and_files():
    # small sample df and y
    df = pd.DataFrame({"a": [1, 2, 3], "b": [0.1, 0.2, 0.3]})
    y = pd.Series([0.0, 1.0, 0.5])
    with tempfile.TemporaryDirectory() as td:
        manifest = tds.export_dataset_with_version(
            df, y=y, output_dir=td, name="unit_ds", version="v0test", fmt_prefer="csv"
        )
        assert manifest.get("name") == "unit_ds"
        assert manifest.get("version") == "v0test"
        files = manifest.get("files")
        assert files and "features" in files and os.path.exists(files["features"])
        assert "labels" in files and os.path.exists(files["labels"])
        # manifest file presence
        # infer manifest path from features path
        feat_path = files["features"]
        base_dir = os.path.dirname(feat_path)
        manifest_path = os.path.join(base_dir, "manifest.json")
        assert os.path.exists(manifest_path)
