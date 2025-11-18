import pandas as pd

from backend.services import training_data_service


def test_build_training_sample_monkeypatched(monkeypatch):
    fake_ctx = {
        "playerId": 1,
        "recentGamesRaw": [
            {"gameDate": "2024-10-01", "PTS": 20},
            {"gameDate": "2024-10-03", "PTS": 25},
        ],
        "seasonStats": {"PTS": 22.5},
    }

    # Patch the nba_service call used inside build_training_sample
    monkeypatch.setattr(
        "backend.services.nba_service.get_player_context_for_training",
        lambda player, stat, game_date, season=None: fake_ctx,
    )

    sample = training_data_service.build_training_sample(
        player="Test Player", stat="PTS", game_date="2024-10-05", season="2024-25"
    )

    assert isinstance(sample, dict)
    assert sample.get("player") == "Test Player"
    assert "features" in sample
    assert "recent_mean" in sample["features"]


def test_build_dataset_from_specs_monkeypatched(monkeypatch):
    # Patch build_training_sample to return deterministic feature dicts
    def _fake_build(player, stat, game_date, season=None):
        return {"features": {"recent_mean": 15.0, "recent_std": 1.0}, "label": 21.0}

    monkeypatch.setattr(
        "backend.services.training_data_service.build_training_sample", _fake_build
    )

    specs = [
        {"player": "A", "stat": "PTS", "game_date": "2024-10-01", "season": "2024-25", "label": 21},
        {"player": "B", "stat": "PTS", "game_date": "2024-10-02", "season": "2024-25", "label": 19},
    ]

    X, y = training_data_service.build_dataset_from_specs(specs)

    assert isinstance(X, pd.DataFrame)
    assert isinstance(y, pd.Series)
    assert X.shape[0] == 2
    assert list(y.astype(float)) == [21.0, 19.0]
    assert "recent_mean" in X.columns
