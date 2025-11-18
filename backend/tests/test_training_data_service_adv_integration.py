from backend.services import training_data_service


def test_build_training_sample_includes_advanced(monkeypatch):
    fake_ctx = {
        "playerId": 1,
        "recentGamesRaw": [
            {"gameDate": "2024-10-01", "PTS": 20},
            {"gameDate": "2024-10-03", "PTS": 25},
        ],
        "seasonStats": {"PTS": 22.5},
        "advancedStats": {"PER": 16.5, "TS_PCT": 0.58},
        "advancedStatsMulti": {"aggregated": {"PER": 15.0, "TS_PCT": 0.56}},
        "seasonStatsMulti": {"2023-24": {"PTS": 21.0}, "2022-23": {"PTS": 19.0}},
    }

    monkeypatch.setattr(
        "backend.services.nba_service.get_player_context_for_training",
        lambda player, stat, game_date, season=None: fake_ctx,
    )

    sample = training_data_service.build_training_sample(
        player="Test Player", stat="PTS", game_date="2024-10-05", season="2024-25"
    )

    feats = sample.get("features", {})
    assert isinstance(feats, dict)
    assert "recent_mean" in feats
    assert "adv_PER" in feats and feats["adv_PER"] == 16.5
    assert "multi_PER" in feats and feats["multi_PER"] == 15.0
    assert "multi_season_PTS_avg" in feats and feats["multi_season_PTS_avg"] == 20.0
