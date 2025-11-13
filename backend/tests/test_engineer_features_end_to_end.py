import pandas as pd
import numpy as np
from backend.services.feature_engineering import engineer_features


def test_engineer_features_end_to_end_columns_and_types():
    # recentGames are newest-first
    player_data = {
        "seasonAvg": 27.5,
        "contextualFactors": {"homeAway": "home", "daysRest": 0},
        "recentGames": [
            {"date": "2025-11-05", "statValue": 30, "opponentTeamId": "BOS", "opponentDefRating": 105.0},
            {"date": "2025-11-02", "statValue": 22, "opponentTeamId": "NYK", "opponentDefRating": 110.0},
            {"date": "2025-10-30", "statValue": 25, "opponentTeamId": "BOS", "opponentDefRating": 105.0},
        ],
    }

    opponent_data = {"teamId": "BOS", "defensiveRating": 105.0, "pace": 98.5}

    df = engineer_features(player_data, opponent_data)

    # Sanity: returns a DataFrame with one row
    assert isinstance(df, pd.DataFrame)
    assert df.shape[0] == 1

    expected_numeric_cols = [
        "recent_mean",
        "recent_std",
        "season_avg",
        "is_home",
        "days_rest",
        "is_back_to_back",
        "last_3_avg",
        "last_5_avg",
        "last_10_avg",
        "exponential_moving_avg",
        "wma_3",
        "wma_5",
        "last_3_std",
        "last_3_min",
        "last_3_max",
        "last_3_median",
        "slope_10",
        "momentum_vs_5_avg",
        "opp_def_rating",
        "opp_pace",
        "games_vs_current_opponent",
        "avg_vs_current_opponent",
        "avg_vs_stronger_def",
        "avg_vs_similar_def",
        "last_game_vs_current_opponent_stat",
    ]

    for col in expected_numeric_cols:
        assert col in df.columns, f"Missing expected column {col}"
        # dtype kind: f=float, i=int, u=unsigned int
        kind = df[col].dtype.kind
        assert kind in ("f", "i", "u"), f"Column {col} expected numeric dtype, got {df[col].dtype}"

    # date column should be present (object/string) or numeric if encoded
    date_col = "last_game_vs_current_opponent_date"
    assert date_col in df.columns
    # value should equal the most recent matching date
    assert str(df.loc[0, date_col]) == "2025-11-05"
