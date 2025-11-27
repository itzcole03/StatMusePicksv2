import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.scripts.train_orchestrator import main as orchestrator_main


def make_player_df(player_name: str, n: int, start_date: str = "2020-01-01"):
    dates = pd.date_range(start=start_date, periods=n, freq="D")
    df = pd.DataFrame(
        {
            "player": [player_name] * n,
            "game_date": dates,
            "target": np.linspace(10.0, 10.0 + n - 1, n),
        }
    )
    return df


def run():
    work = Path.cwd() / "tmp_debug"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()

    train = make_player_df("Test Player", 5)
    val = make_player_df("Test Player", 3, start_date="2020-02-01")
    test = make_player_df("Test Player", 2, start_date="2020-03-01")

    d = work / "data"
    d.mkdir()
    t = d / "train.parquet"
    v = d / "val.parquet"
    te = d / "test.parquet"
    train.to_parquet(t)
    val.to_parquet(v)
    test.to_parquet(te)

    manifest = {
        "parts": {
            "train": {"files": {"features": str(t)}},
            "val": {"files": {"features": str(v)}},
            "test": {"files": {"features": str(te)}},
        }
    }
    manifest_path = work / "manifest.json"
    with open(manifest_path, "w", encoding="utf8") as fh:
        json.dump(manifest, fh)

    models_dir = work / "models"
    orchestrator_main(
        str(manifest_path),
        min_games=1,
        out_dir=str(models_dir),
        report_csv=str(work / "report.csv"),
        limit=None,
        workers=1,
        fit_calibrators=True,
    )

    print("Models dir listing:")
    for p in sorted(models_dir.glob("*")):
        print(" -", p.name)

    calib_file = models_dir / "Test_Player_calibrator.pkl"
    print("Calibrator exists:", calib_file.exists(), calib_file)
    # Attempt explicit calibrator fit using the saved model and val split to see errors
    try:
        from backend.services import calibration_service as calib_mod
        from backend.services.model_registry import ModelRegistry

        registry = ModelRegistry(model_dir=str(models_dir))
        model = registry.load_model("Test Player")
        if model is None:
            print("Could not load model for explicit calibrator check")
            return
        val_path = work / "data" / "val.parquet"
        df_val = pd.read_parquet(val_path)
        # build lag features consistent with orchestrator
        df_val = df_val.sort_values("game_date").reset_index(drop=True)
        df_val["lag_1"] = df_val["target"].shift(1).fillna(df_val["target"].mean())
        df_val["lag_3_mean"] = (
            df_val["target"]
            .shift(1)
            .rolling(window=3, min_periods=1)
            .mean()
            .fillna(df_val["target"].mean())
        )
        feat_cols = ["lag_1", "lag_3_mean"]
        X_val = df_val[feat_cols].select_dtypes(include=["number"]).fillna(0)
        y_val = df_val["target"].astype(float).to_numpy()
        try:
            y_pred = model.predict(X_val)
        except Exception:
            y_pred = model.predict(X_val.values)

        calib = calib_mod.CalibrationService(model_dir=str(models_dir))
        info = calib.fit_and_save(
            "Test Player", y_true=y_val, y_pred=y_pred, method="isotonic"
        )
        print("Explicit fit result:", info)
    except Exception as e:
        print("Explicit calibrator fit failed:", e)


if __name__ == "__main__":
    run()
