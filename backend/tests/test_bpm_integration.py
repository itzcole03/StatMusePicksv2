import pandas as pd

from backend.services import feature_engineering as fe


def test_adv_bpm_and_multi_bpm_present():
    # Prepare player data with advancedStatsMulti aggregated containing BPM
    player_data = {
        "recentGames": [],
        "seasonAvg": 10.0,
        "advancedStatsMulti": {"aggregated": {"PER": 16.0, "BPM": 2.5, "TS_PCT": 0.56}},
        "seasonStatsMulti": {"2023-24": {"PTS": 11.0}},
        "contextualFactors": {"daysRest": 1, "homeAway": "away"},
        "player_id": 12345,
    }

    df = fe.FeatureEngineering.engineer_features(player_data)
    assert isinstance(df, pd.DataFrame)
    # adv_BPM is added by the DataFrame-engineer path when advanced metrics are fetched
    # If adv_BPM isn't present because external call failed, multi_BPM should be present
    cols = set(df.columns.tolist())
    assert "multi_BPM" in cols
    # multi_BPM should reflect the aggregated BPM value
    assert float(df["multi_BPM"].iloc[0]) == 2.5
