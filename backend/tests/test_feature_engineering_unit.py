import pandas as pd

from backend.services.feature_engineering import engineer_features


def test_engineer_features_basic():
    player_data = {
        "recentGames": [
            {"gameDate": "2025-01-01", "statValue": 20},
            {"gameDate": "2025-01-03", "statValue": 25},
            {"gameDate": "2025-01-05", "statValue": 30},
        ],
        "seasonAvg": 25,
        "contextualFactors": {"homeAway": "home", "daysRest": 2},
    }

    df = engineer_features(player_data)
    # should return a single-row DataFrame
    assert isinstance(df, pd.DataFrame)
    assert df.shape[0] == 1

    # expected columns present
    expected_cols = ["recent_mean", "recent_std", "season_avg", "is_home", "days_rest"]
    for c in expected_cols:
        assert c in df.columns

    # values are numeric / non-null after fillna
    assert float(df.iloc[0]["recent_mean"]) > 0
