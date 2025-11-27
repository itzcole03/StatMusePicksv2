import sys
from pathlib import Path

import numpy as np
import pandas as pd


def _ensure_repo_on_path():
    ROOT = Path.cwd()
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


def make_player_df(
    player_name: str, n: int, start_date: str = "2020-01-01"
) -> pd.DataFrame:
    dates = pd.date_range(start=start_date, periods=n, freq="D")
    df = pd.DataFrame(
        {
            "player": [player_name] * n,
            "game_date": dates,
            "target": np.linspace(10.0, 10.0 + n - 1, n),
        }
    )
    return df


def test_orchestrator_trains_and_fits_calibrator(tmp_path):
    _ensure_repo_on_path()
    # Imports from repo now that root is on sys.path
    from backend.scripts.train_orchestrator import main as orchestrator_main
    from backend.services.model_registry import ModelRegistry

    # Prepare tiny dataset with one player having train+val rows
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    train_df = make_player_df("Test Player", 5)
    val_df = make_player_df("Test Player", 3, start_date="2020-02-01")
    test_df = make_player_df("Test Player", 2, start_date="2020-03-01")

    train_path = data_dir / "train_features.parquet"
    val_path = data_dir / "val_features.parquet"
    test_path = data_dir / "test_features.parquet"
    train_df.to_parquet(train_path)
    val_df.to_parquet(val_path)
    test_df.to_parquet(test_path)

    manifest = {
        "parts": {
            "train": {"files": {"features": str(train_path)}},
            "val": {"files": {"features": str(val_path)}},
            "test": {"files": {"features": str(test_path)}},
        }
    }
    manifest_path = tmp_path / "manifest.json"
    import json

    with open(manifest_path, "w", encoding="utf8") as fh:
        json.dump(manifest, fh)

    models_dir = tmp_path / "models"
    report_csv = tmp_path / "report.csv"

    # Run orchestrator serially and request calibrator fitting
    orchestrator_main(
        str(manifest_path),
        min_games=1,
        out_dir=str(models_dir),
        report_csv=str(report_csv),
        limit=None,
        workers=1,
        fit_calibrators=True,
    )

    # Check model + calibrator saved
    registry = ModelRegistry(model_dir=str(models_dir))
    mdl = registry.load_model("Test Player")
    assert mdl is not None, "Expected trained model to be saved"
    calib = registry.load_calibrator("Test Player")
    assert calib is not None, "Expected calibrator to be saved when enough val rows"


def test_align_features_adds_missing_columns(tmp_path):
    _ensure_repo_on_path()
    # import align_features from compute script
    import scripts.compute_calibration_metrics as ccm
    from backend.services.training_pipeline import train_player_model

    # Train a model on data containing an extra feature
    df = pd.DataFrame(
        {
            "lag_1": [1.0, 2.0, 3.0, 4.0],
            "lag_3_mean": [1.0, 1.5, 2.0, 2.5],
            "extra_feat": [10.0, 11.0, 12.0, 13.0],
            "target": [5.0, 6.0, 7.0, 8.0],
        }
    )
    model = train_player_model(df, target_col="target")

    # Create validation X missing the `extra_feat` column
    X_val = pd.DataFrame(
        {
            "lag_1": [2.0, 3.0, 4.0],
            "lag_3_mean": [1.5, 2.0, 2.5],
        }
    )

    X_aligned = ccm.align_features(X_val.copy(), model)

    # Model was trained with 'extra_feat' so align_features should add it
    assert "extra_feat" in X_aligned.columns, "Expected missing column to be added"
    # values for the added column should be numeric zeros
    assert all(X_aligned["extra_feat"].fillna(0.0) == 0.0)
