import importlib

import numpy as np
import pandas as pd


def _mod():
    return importlib.import_module("backend.services.training_pipeline")


def test_train_player_model_with_advanced_multi_features():
    tp = _mod()
    df = pd.DataFrame(
        {
            "multi_PER": [12.0, 13.0],
            "multi_TS_PCT": [0.55, 0.57],
            "multi_USG_PCT": [20.0, 21.0],
            "multi_season_PTS_avg": [14.0, 15.0],
            "multi_season_count": [2, 2],
            "multi_PIE": [10.0, 11.0],
            "multi_off_rating": [105.0, 106.0],
            "multi_def_rating": [99.0, 98.5],
            "last_3_avg": [10.0, 12.0],
            "target": [11.0, 13.0],
        }
    )

    model = tp.train_player_model(df, target_col="target")
    X = df.drop(columns=["target"]).select_dtypes(include=[np.number]).fillna(0)
    preds = model.predict(X)
    assert len(preds) == 2
