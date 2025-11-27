import datetime
import importlib

import pandas as pd


def _client():
    return importlib.import_module("backend.services.nba_stats_client")


def _svc():
    return importlib.import_module("backend.services.nba_service")


def _fe():
    return importlib.import_module("backend.services.feature_engineering")


def _tds():
    return importlib.import_module("backend.services.training_data_service")


def _make_games(n=30, start_date=datetime.date(2022, 1, 1)):
    games = []
    for i in range(n):
        d = start_date + datetime.timedelta(days=i * 2)
        games.append(
            {
                "GAME_DATE": d.isoformat(),
                "gameDate": d.isoformat(),
                "PTS": 10 + i,
                "AST": 1 + (i % 3),
                "REB": 5 + (i % 2),
                "MATCHUP": "TEAM vs OPP",
                "TEAM_ID": 1610612739,
                "opponentDefRating": 105.0,
                "opponentTeamId": 1610612740,
                "statValue": 10 + i,
            }
        )
    return games


def test_e2e_context_to_features_and_training(monkeypatch):
    client = _client()
    svc = _svc()
    fe = _fe()
    tds = _tds()

    # Patch client lookups to deterministic cached data
    monkeypatch.setattr(client, "find_player_id_by_name", lambda name: 999)
    games = _make_games(40)
    monkeypatch.setattr(
        client, "fetch_recent_games", lambda pid, lim, season: games[:lim]
    )
    monkeypatch.setattr(
        client, "fetch_recent_games_multi", lambda pid, seasons, limit_per_season: games
    )
    monkeypatch.setattr(
        client, "get_player_season_stats", lambda pid, season: {"PTS": 15.0}
    )
    monkeypatch.setattr(
        client,
        "get_advanced_player_stats",
        lambda pid, season: {
            "PER": 12.5,
            "TS_PCT": 0.56,
            "USG_PCT": 21.0,
            "PIE": 9.5,
            "OFF_RATING": 105.0,
            "DEF_RATING": 99.0,
        },
    )
    monkeypatch.setattr(
        client,
        "get_player_season_stats_multi",
        lambda pid, seasons: {s: {"PTS": 14.0 + i} for i, s in enumerate(seasons)},
    )
    monkeypatch.setattr(
        client,
        "get_advanced_player_stats_multi",
        lambda pid, seasons: {
            "per_season": {s: {"PER": 11.0 + i} for i, s in enumerate(seasons)},
            "aggregated": {"PER": 11.5, "TS_PCT": 0.55},
        },
    )
    monkeypatch.setattr(
        client,
        "get_team_stats_multi",
        lambda tid, seasons: {s: {"PTS_avg": 110 + i} for i, s in enumerate(seasons)},
    )
    monkeypatch.setattr(
        client,
        "get_advanced_team_stats_multi",
        lambda tid, seasons: {
            "per_season": {s: {"OFF_RATING": 104 + i} for i, s in enumerate(seasons)},
            "aggregated": {"OFF_RATING": 105.0},
        },
    )

    # 1) get_player_context_for_training
    ctx = svc.get_player_context_for_training(
        "Any Player", "points", "2023-02-01", "2023-24"
    )
    assert isinstance(ctx, dict)
    assert "seasonStatsMulti" in ctx and isinstance(ctx["seasonStatsMulti"], dict)
    assert "advancedStatsMulti" in ctx and isinstance(ctx["advancedStatsMulti"], dict)

    # 2) engineer features from the context
    features_df = fe.engineer_features(ctx)
    assert hasattr(features_df, "iloc")
    # ensure multi-season columns exist and numeric
    for col in ("multi_PER", "multi_season_PTS_avg", "multi_PIE", "multi_off_rating"):
        assert col in features_df.columns
        assert isinstance(float(features_df.iloc[0][col]), float)

    # 3) generate training data (uses fetch_recent_games or multi-version)
    train_df = tds.generate_training_data(
        "Any Player",
        stat="points",
        min_games=5,
        fetch_limit=100,
        seasons=["2021-22", "2022-23"],
    )
    assert isinstance(train_df, pd.DataFrame)
    assert "target" in train_df.columns
    assert len(train_df) > 0
