import pytest

from backend.services import feature_engineering


def sample_recent_games():
    # 5 recent games with statValue
    return [
        {"date": "2025-11-01", "statValue": 20},
        {"date": "2025-11-03", "statValue": 25},
        {"date": "2025-11-05", "statValue": 22},
        {"date": "2025-11-07", "statValue": 30},
        {"date": "2025-11-09", "statValue": 18},
    ]


def test_recent_stats_from_games():
    recent = sample_recent_games()
    stats = feature_engineering.recent_stats_from_games(recent)
    assert stats["sample_size"] == 5
    assert pytest.approx(stats["mean"], rel=1e-3) == sum([20, 25, 22, 30, 18]) / 5
    assert stats["median"] == 22
    assert stats["std"] >= 0
    assert stats["trend_slope"] is not None


def test_calculate_rolling_averages():
    recent = sample_recent_games()
    rolls = feature_engineering.calculate_rolling_averages(recent)
    assert rolls["last_3_avg"] == pytest.approx((20 + 25 + 22) / 3)
    assert rolls["last_5_avg"] == pytest.approx((20 + 25 + 22 + 30 + 18) / 5)
    assert "exponential_moving_avg" in rolls


def test_engineer_features_dataframe():
    player_data = {"recentGames": sample_recent_games(), "seasonAvg": 23.0, "contextualFactors": {"homeAway": "home", "daysRest": 2}}
    df = feature_engineering.engineer_features(player_data, opponent_data={"defensiveRating": 110, "pace": 98.5})
    assert df.shape[0] == 1
    # columns we expect
    for col in ["recent_mean", "recent_std", "season_avg", "is_home", "days_rest", "last_3_avg", "exponential_moving_avg"]:
        assert col in df.columns
    assert int(df.loc[0, "is_home"]) == 1


def test_back_to_back_indicator():
    player_data = {"recentGames": sample_recent_games(), "seasonAvg": 20.0, "contextualFactors": {"homeAway": "away", "daysRest": 0}}
    df = feature_engineering.engineer_features(player_data)
    assert df.shape[0] == 1
    assert "is_back_to_back" in df.columns
    assert int(df.loc[0, "is_back_to_back"]) == 1


def test_engineer_features_multiple_players():
    # Create 10 different player inputs with varying recent games and rest
    for i in range(10):
        recent = [
            {"date": f"2025-11-{1 + j:02d}", "statValue": 10 + i + j}
            for j in range(3 + (i % 3))
        ]
        player_data = {
            "recentGames": recent,
            "seasonAvg": 12.0 + i,
            "contextualFactors": {"homeAway": "home" if i % 2 == 0 else "away", "daysRest": i % 4},
        }
        df = feature_engineering.engineer_features(player_data)
        assert df.shape[0] == 1
        assert "is_back_to_back" in df.columns
