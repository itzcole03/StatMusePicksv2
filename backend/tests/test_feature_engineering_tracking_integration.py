import json

from backend.services.feature_engineering import engineer_features


def test_engineer_includes_tracking_features(tmp_path):
    # prepare tracking data dir
    data_dir = tmp_path / "tracking"
    data_dir.mkdir()

    sample = [
        {
            "game_date": "2025-11-01",
            "avg_speed_mph": 6.2,
            "distance_m": 4800,
            "touches": 11,
            "time_of_possession_sec": 40,
            "exp_fg_pct": 0.5,
        }
    ]

    player_name = "Integration Player"
    fname = data_dir / ("integration_player.json")
    with open(fname, "w", encoding="utf-8") as fh:
        json.dump(sample, fh)

    # player_data expected by feature_engineering; engineer_features will call tracking service
    player_data = {
        "playerName": player_name,
        "recentGames": [],
        # ensure feature_engineering can locate tracking files via default path argument in service
    }

    # monkeypatch default tracking dir by setting environment or passing via player_data not available;
    # Instead, set backend.services.player_tracking_service._default_data_dir to tmp path at runtime
    try:
        from backend.services import player_tracking_service as _trk

        # monkeypatch the default data dir for the service
        _trk._default_data_dir = lambda: str(data_dir)
    except Exception:
        pass

    df = engineer_features(player_data)
    cols = list(df.columns)

    # expect tracking-derived prefixed features to be present
    assert any(c.startswith("trk_") for c in cols), f"No trk_ features found in {cols}"
