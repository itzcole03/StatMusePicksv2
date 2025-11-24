import os
import importlib

import pytest

from backend.services import per_ws_from_playbyplay
from backend.services import nba_stats_client


def make_sample_games():
    # single-season sample with one game; values chosen to be simple
    return [
        {
            'PTS': 30,
            'AST': 5,
            'REB': 10,
            'FGA': 20,
            'FGM': 10,
            'FTA': 5,
            'FTM': 4,
            'STL': 2,
            'BLK': 1,
            'TOV': 3,
            'MIN': 36,
        }
    ]


def test_per_ws_scale_monkeypatch():
    games = make_sample_games()
    agg = per_ws_from_playbyplay.aggregate_season_games(games)
    out = per_ws_from_playbyplay.compute_per_ws_from_aggregates(agg)

    # record raw values
    raw_per = out.get('PER_est_raw')
    raw_ws_per_game = out.get('ws_per_game')
    raw_ws_season = out.get('WS_est_raw')
    games_count = agg.get('games')
    assert games_count == 1

    # monkeypatch scales and verify PER/WS reflect the multiplier
    orig_per = per_ws_from_playbyplay.PER_SCALE
    orig_ws = per_ws_from_playbyplay.WS_SCALE
    try:
        per_ws_from_playbyplay.PER_SCALE = 0.5
        per_ws_from_playbyplay.WS_SCALE = 0.25
        out2 = per_ws_from_playbyplay.compute_per_ws_from_aggregates(agg)
        assert pytest.approx(out2['PER_est'], rel=1e-6) == raw_per * 0.5
        # `WS_est_raw` is the unscaled season WS total; WS_est should equal that * WS_SCALE
        assert pytest.approx(out2['WS_est'], rel=1e-6) == raw_ws_season * 0.25
    finally:
        per_ws_from_playbyplay.PER_SCALE = orig_per
        per_ws_from_playbyplay.WS_SCALE = orig_ws


def test_get_advanced_player_stats_fallback_uses_prototype(monkeypatch):
    # monkeypatch fetch_recent_games to return our sample games
    sample_games = make_sample_games()

    def fake_fetch_recent_games(pid, limit=500, season=None):
        return sample_games

    monkeypatch.setattr(nba_stats_client, 'fetch_recent_games', fake_fetch_recent_games)

    # ensure prototype scales are known for the assertion
    orig_per = per_ws_from_playbyplay.PER_SCALE
    orig_ws = per_ws_from_playbyplay.WS_SCALE
    try:
        per_ws_from_playbyplay.PER_SCALE = 0.6
        per_ws_from_playbyplay.WS_SCALE = 0.4

        stats = nba_stats_client.get_advanced_player_stats_fallback(12345, '2024-25')
        assert 'PER' in stats and stats['PER'] is not None
        assert 'WS' in stats and stats['WS'] is not None

        # recompute expected via prototype
        agg = per_ws_from_playbyplay.aggregate_season_games(sample_games)
        est = per_ws_from_playbyplay.compute_per_ws_from_aggregates(agg)

        assert pytest.approx(stats['PER'], rel=1e-6) == est['PER_est']
        assert pytest.approx(stats['WS'], rel=1e-6) == est['WS_est']
    finally:
        per_ws_from_playbyplay.PER_SCALE = orig_per
        per_ws_from_playbyplay.WS_SCALE = orig_ws
