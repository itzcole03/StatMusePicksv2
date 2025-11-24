import pandas as pd
import numpy as np
import pytest

from backend.services import training_pipeline
from backend.scripts import compare_advanced_vs_baseline as compare_script


def make_training_df(n_rows=10):
    # simple DataFrame with numeric features and a target
    rng = np.random.RandomState(42)
    df = pd.DataFrame({
        'feat1': rng.randn(n_rows),
        'feat2': rng.randn(n_rows) * 2.0,
        'target': rng.randn(n_rows) * 0.5 + 1.0,
    })
    return df


def test_train_player_model_basic():
    df = make_training_df(20)
    model = training_pipeline.train_player_model(df, target_col='target')
    # model should implement predict
    assert hasattr(model, 'predict')
    # predict on first few rows
    X = df.drop(columns=['target']).select_dtypes(include=[np.number])
    preds = model.predict(X)
    assert len(preds) == len(X)


def test_compare_evaluate_player_handles_insufficient(monkeypatch):
    # monkeypatch generate_training_data to return a tiny df (1 row)
    small_df = make_training_df(1)

    def fake_generate_training_data(player, min_games=1, fetch_limit=300, seasons=None):
        return small_df

    monkeypatch.setattr('backend.services.training_data_service.generate_training_data', fake_generate_training_data)
    # monkeypatch augment_with_llm to no-op
    monkeypatch.setattr(compare_script, 'augment_with_llm', lambda df, player: df)

    res = compare_script.evaluate_player('Test Player', min_games=1)
    assert res['status'] in ('insufficient_rows', 'no_data', 'ok')
