import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from backend.scripts.train_orchestrator import _train_worker

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    data_dir = td / "data"
    data_dir.mkdir()

    def make_player_df(player_name, n, start_date="2020-01-01"):
        dates = pd.date_range(start=start_date, periods=n, freq="D")
        df = pd.DataFrame(
            {
                "player": [player_name] * n,
                "game_date": dates,
                "target": np.linspace(10.0, 10.0 + n - 1, n),
            }
        )
        return df

    train = make_player_df("Test Player", 5)
    val = make_player_df("Test Player", 3, start_date="2020-02-01")
    test = make_player_df("Test Player", 2, start_date="2020-03-01")
    train_path = data_dir / "train_features.parquet"
    val_path = data_dir / "val_features.parquet"
    test_path = data_dir / "test_features.parquet"
    train.to_parquet(train_path)
    val.to_parquet(val_path)
    test.to_parquet(test_path)
    manifest = {
        "parts": {
            "train": {"files": {"features": str(train_path)}},
            "val": {"files": {"features": str(val_path)}},
            "test": {"files": {"features": str(test_path)}},
        }
    }
    manifest_path = td / "manifest.json"
    with open(manifest_path, "w", encoding="utf8") as fh:
        json.dump(manifest, fh)
    models_dir = td / "models"
    report_csv = td / "report.csv"
    # Call worker directly to capture return value including cal_info
    kw = {
        "manifest": str(manifest_path),
        "player": "Test Player",
        "out_dir": str(models_dir),
        "fit_calibrator": True,
        "tune": False,
    }
    result = _train_worker(kw)
    print("Worker result:", result)
    print("Models dir contents:")
    for p in sorted(models_dir.rglob("*")):
        print(p)
    calib = models_dir / "Test_Player_calibrator.pkl"
    print("Calibrator path expected:", calib)
    print("Exists:", calib.exists())
    # Try to reproduce calibrator fit manually for debugging
    try:
        from backend.services.calibration_service import CalibrationService
        from backend.services.model_registry import ModelRegistry

        registry = ModelRegistry(model_dir=str(models_dir))
        loaded = registry.load_model("Test Player")
        print("Loaded model:", type(loaded))
        val_df = pd.read_parquet(val_path)
        val_df["game_date"] = pd.to_datetime(val_df["game_date"]).dt.tz_localize(None)
        from backend.scripts.train_orchestrator import build_lag_features

        v = build_lag_features(val_df)
        feat_cols = ["lag_1", "lag_3_mean"]
        X_val = v[feat_cols].copy()
        # Attempt alignment similar to orchestrator worker
        try:
            if hasattr(loaded, "_feature_list") and getattr(
                loaded, "_feature_list", None
            ):
                expected = list(getattr(loaded, "_feature_list"))
            elif hasattr(loaded, "feature_names_in_"):
                expected = list(loaded.feature_names_in_)
                for c in expected:
                    if c not in X_val.columns:
                        X_val[c] = 0.0
                X_val = X_val.reindex(columns=expected)
            elif hasattr(loaded, "estimators_") and len(loaded.estimators_) > 0:
                est = loaded.estimators_[0]
                if hasattr(est, "feature_names_in_"):
                    expected = list(est.feature_names_in_)
                    for c in expected:
                        if c not in X_val.columns:
                            X_val[c] = 0.0
                    X_val = X_val.reindex(columns=expected)
            # Debug prints
            try:
                print("Expected feature count:", len(expected))
                print("Expected head:", expected[:10])
                print(
                    "X_val columns after alignment attempt:", list(X_val.columns)[:15]
                )
            except Exception:
                pass
        except Exception:
            import traceback

            print("Alignment failed with exception:")
            traceback.print_exc()
            X_val = X_val.select_dtypes(include=["number"]).fillna(0)

        X_val = X_val.select_dtypes(include=["number"]).fillna(0)
        y_val = v["target"].astype(float).to_numpy()
        try:
            y_pred = loaded.predict(X_val)
        except Exception:
            import traceback

            print("Predict on DataFrame failed, trying numpy array. Exception:")
            traceback.print_exc()
            y_pred = loaded.predict(X_val.values)
        print("y_val shape, y_pred shape:", y_val.shape, y_pred.shape)
        calib_service = CalibrationService(model_dir=str(models_dir))
        res = calib_service.fit_and_save(
            "Test Player", y_true=y_val, y_pred=y_pred, method="isotonic"
        )
        print("fit_and_save result:", res)
    except Exception as e:
        import traceback

        print("Manual calibrator reproduction failed:")
        traceback.print_exc()
