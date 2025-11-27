import os
import tempfile
from datetime import date, timedelta

import pandas as pd

from backend.services import training_data_service as tds


def _make_df(n=20):
    start = date(2020, 1, 1)
    dates = [start + timedelta(days=i) for i in range(n)]
    df = pd.DataFrame(
        {
            "game_date": dates,
            "feat1": list(range(n)),
            "feat2": [float(i) * 0.5 for i in range(n)],
        }
    )
    y = pd.Series([float(i) for i in range(n)])
    return df, y


def test_chronological_split_by_ratio_counts_and_order():
    df, y = _make_df(20)
    train, val, test = tds.chronological_split_by_ratio(
        df, date_col="game_date", train_frac=0.7, val_frac=0.15, test_frac=0.15
    )
    assert len(train) == 14
    assert len(val) == 3
    assert len(test) == 3
    # ensure chronological order preserved
    assert train["game_date"].max() <= val["game_date"].min()
    assert val["game_date"].max() <= test["game_date"].min()


def test_export_dataset_with_version_csv_fallback_and_manifest():
    df, y = _make_df(5)
    with tempfile.TemporaryDirectory() as td:
        manifest = tds.export_dataset_with_version(
            df, y=y, output_dir=td, name="unittest", version="v0", fmt_prefer="csv"
        )
        assert manifest.get("name") == "unittest"
        assert "rows" in manifest and manifest["rows"] == 5
        files = manifest.get("files")
        assert files is not None
        feat_path = files.get("features")
        assert feat_path and os.path.exists(feat_path)
        # read back and verify shape
        read_df = pd.read_csv(feat_path, compression="gzip")
        assert len(read_df) == 5
        # labels present
        labels_path = files.get("labels")
        assert labels_path and os.path.exists(labels_path)
        read_y = pd.read_csv(labels_path, compression="gzip")
        assert len(read_y) == 5
