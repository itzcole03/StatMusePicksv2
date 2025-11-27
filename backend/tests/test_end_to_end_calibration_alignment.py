import numpy as np
import pandas as pd

from backend.services.calibration_service import CalibrationService
from backend.services.model_registry import ModelRegistry
from backend.services.training_pipeline import train_player_model


def test_end_to_end_calibration_alignment(tmp_path):
    # Build small synthetic train/val dataset with known features
    rng = np.random.RandomState(0)
    n_train = 30
    n_val = 10
    X_train = pd.DataFrame(
        {
            "f1": rng.normal(size=n_train),
            "f2": rng.normal(size=n_train),
        }
    )
    y_train = (
        X_train["f1"] * 2.0 + X_train["f2"] * -0.5 + rng.normal(scale=0.1, size=n_train)
    )
    train_df = X_train.copy()
    train_df["target"] = y_train

    X_val = pd.DataFrame(
        {
            "f1": rng.normal(size=n_val),
            "f2": rng.normal(size=n_val),
        }
    )
    y_val = X_val["f1"] * 2.0 + X_val["f2"] * -0.5 + rng.normal(scale=0.1, size=n_val)
    val_df = X_val.copy()
    val_df["target"] = y_val

    # Train model using training_pipeline
    model = train_player_model(train_df, target_col="target")
    # ensure feature list persisted on model
    assert hasattr(model, "_feature_list")
    # Save model via registry
    model_dir = tmp_path / "models"
    reg = ModelRegistry(model_dir=str(model_dir))
    reg.save_model("E2E Player", model, version="v1", notes="e2e")

    # Prepare validation features aligned to persisted feature list
    feat_list = getattr(model, "_feature_list")
    X_val_aligned = X_val.copy()
    for c in feat_list:
        if c not in X_val_aligned.columns:
            X_val_aligned[c] = 0.0
    X_val_aligned = X_val_aligned.reindex(columns=feat_list)

    # Get raw predictions from model (via registry.load_model to mimic serving)
    loaded = reg.load_model("E2E Player")
    assert loaded is not None
    try:
        raw_preds = loaded.predict(X_val_aligned)
    except Exception:
        raw_preds = loaded.predict(X_val_aligned.values)

    # Fit calibrator and persist
    calib_service = CalibrationService(model_dir=str(model_dir))
    res = calib_service.fit_and_save(
        "E2E Player", y_true=y_val, y_pred=raw_preds, method="isotonic"
    )
    assert "before" in res and "after" in res

    # Reload calibrator and apply
    calib = calib_service.load_calibrator("E2E Player")
    assert calib is not None
    out = calib_service.calibrate("E2E Player", raw_preds)
    assert len(out) == len(raw_preds)
