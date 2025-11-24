def test_features_for_player_no_data_returns_keys():
    """Ensure the tracking service returns a dict with expected keys and safe values."""
    from backend.services.player_tracking_service import features_for_player

    res = features_for_player("Nonexistent Player For Test", seasons=None)
    assert isinstance(res, dict)

    expected_keys = [
        "avg_speed",
        "distance_per_game",
        "touches_per_game",
        "time_of_possession",
        "shot_quality",
    ]
    for k in expected_keys:
        assert k in res

    # values should be numeric (int/float) or None
    for v in res.values():
        assert v is None or isinstance(v, (int, float))


def test_engineer_features_basic_call():
    """Basic smoke test: calling engineer_features with empty data returns a DataFrame-like object."""
    from backend.services.feature_engineering import engineer_features

    df = engineer_features({})
    # minimal checks
    assert hasattr(df, "shape")
    assert df.shape[0] == 1
