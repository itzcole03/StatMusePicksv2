from backend.services.feature_engineering import calculate_rolling_averages, engineer_features


def test_calculate_rolling_averages_simple():
    recent_games = [
        {"date": "2025-01-01", "statValue": 20},
        {"date": "2025-01-02", "statValue": 25},
        {"date": "2025-01-03", "statValue": 30},
        {"date": "2025-01-04", "statValue": 28},
    ]

    out = calculate_rolling_averages(recent_games, windows=[3, 5])

    assert "last_3_avg" in out
    assert out["last_3_avg"] == (20 + 25 + 30) / 3
    assert "last_5_avg" in out
    assert out["last_5_avg"] is None
    assert "exponential_moving_avg" in out
    assert isinstance(out["exponential_moving_avg"], float)


def test_engineer_features_minimal():
    player_data = {
        "recentGames": [
            {"date": "2025-01-01", "statValue": 10},
            {"date": "2025-01-02", "statValue": 12},
        ],
        "seasonAvg": 11.0,
        "contextualFactors": {"homeAway": "home", "daysRest": 2},
    }

    df = engineer_features(player_data)
    assert df.shape[0] == 1
    assert "recent_mean" in df.columns
    assert df["is_home"].iloc[0] == 1
