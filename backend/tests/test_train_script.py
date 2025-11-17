import pandas as pd
import pytest

from backend.scripts import train_and_persist_real_model as trainer


def test_build_dataset_wiring(monkeypatch):
    # Monkeypatch nba_service to return a context with multiple recent games
    fake_ctx = {
        'playerId': 1,
        'recentGamesRaw': [
            {'gameDate': '2024-10-05', 'PTS': 15, 'statValue': 15},
            {'gameDate': '2024-10-03', 'PTS': 12, 'statValue': 12},
            {'gameDate': '2024-10-01', 'PTS': 10, 'statValue': 10},
        ],
        'seasonStats': {'PTS': 12.33},
    }

    monkeypatch.setattr(
        'backend.services.nba_service.get_player_context_for_training',
        lambda player, stat, game_date, season: fake_ctx,
    )

    # Monkeypatch training_data_service to capture specs and return simple dataset
    def fake_build(specs):
        assert len(specs) >= 1
        return pd.DataFrame([{'recent_mean': 12.0}]), pd.Series([13.0])

    monkeypatch.setattr('backend.services.training_data_service.build_dataset_from_specs', fake_build)

    X, y, feature_names = trainer.build_dataset(n_samples=10)
    # ensure we get dataset back from fake_build
    assert isinstance(X, pd.DataFrame)
    assert isinstance(y, (pd.Series, list))
    assert 'recent_mean' in X.columns
