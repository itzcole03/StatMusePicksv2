import importlib


def _mod():
    return importlib.import_module('backend.services.feature_engineering')


def test_engineer_features_includes_multi_season_fields():
    m = _mod()
    # Build a minimal player_context with recentGames and multi-season data
    player_context = {
        'recentGames': [{'statValue': 20}, {'statValue': 15}, {'statValue': 10}],
        'seasonAvg': 14.0,
        'advancedStatsMulti': {'aggregated': {'PER': 13.5, 'TS_PCT': 0.55, 'USG_PCT': 22.0}},
        'seasonStatsMulti': {'2022-23': {'PTS': 12.0}, '2021-22': {'PTS': 13.0}},
        'contextualFactors': {'daysRest': 1, 'homeAway': 'home'},
    }

    df = m.engineer_features(player_context)
    assert hasattr(df, 'iloc')  # DataFrame-like
    # Ensure multi-season fields are present and numeric for the first row
    assert 'multi_PER' in df.columns
    assert isinstance(df.iloc[0]['multi_PER'], float)
    assert isinstance(df.iloc[0]['multi_TS_PCT'], float)
    assert isinstance(df.iloc[0]['multi_USG_PCT'], float)
    assert isinstance(df.iloc[0]['multi_season_PTS_avg'], float)
    assert int(df.iloc[0]['multi_season_count']) == 2
    # New advanced/team fields
    assert 'multi_PIE' in df.columns and isinstance(df.iloc[0]['multi_PIE'], float)
    assert 'multi_off_rating' in df.columns and isinstance(df.iloc[0]['multi_off_rating'], float)
    assert 'multi_def_rating' in df.columns and isinstance(df.iloc[0]['multi_def_rating'], float)
