import pandas as pd

from backend.services import training_data_service


def test_build_training_sample_monkeypatch(monkeypatch):
    fake_ctx = {
        "playerId": 123,
        "recentGamesRaw": [
            {"gameDate": "2024-10-01", "statValue": 20, "PTS": 20},
            {"gameDate": "2024-10-03", "statValue": 25, "PTS": 25},
        ],
        "seasonStats": {"PTS": 22.5},
    }

    monkeypatch.setattr(
        "backend.services.nba_service.get_player_context_for_training",
        lambda player, stat, game_date, season: fake_ctx,
    )

    sample = training_data_service.build_training_sample(
        "Test Player", "points", "2024-10-03", "2024-25"
    )
    assert isinstance(sample, dict)
    assert sample["player"] == "Test Player"
    assert isinstance(sample["features"], dict)


def test_build_dataset_from_specs_monkeypatch(monkeypatch):
    # Monkeypatch build_training_sample to return consistent features
    monkeypatch.setattr(
        "backend.services.training_data_service.build_training_sample",
        lambda player, stat, game_date, season: {
            "features": {"recent_mean": 20.0, "recent_std": 2.0},
            "raw_context": {},
        },
    )

    specs = [
        {
            "player": "A",
            "stat": "points",
            "game_date": "2024-10-01",
            "season": "2024-25",
            "label": 21,
        },
        {
            "player": "B",
            "stat": "points",
            "game_date": "2024-10-02",
            "season": "2024-25",
            "label": 19,
        },
    ]

    X, y = training_data_service.build_dataset_from_specs(specs)
    assert isinstance(X, pd.DataFrame)
    assert isinstance(y, pd.Series)
    assert X.shape[0] == 2
    assert "recent_mean" in X.columns
    assert list(y) == [21.0, 19.0]
