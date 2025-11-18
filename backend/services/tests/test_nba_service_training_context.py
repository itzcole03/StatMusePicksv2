import importlib


def _mod():
    return importlib.import_module('backend.services.nba_service')


def _client():
    return importlib.import_module('backend.services.nba_stats_client')


def test_get_player_context_for_training_multi(monkeypatch):
    svc = _mod()
    client = _client()

    # Monkeypatch client functions
    monkeypatch.setattr(client, 'find_player_id_by_name', lambda name: 7)
    # recent games: include TEAM_ID
    monkeypatch.setattr(client, 'fetch_recent_games', lambda pid, lim, season: [{'GAME_DATE': '2024-01-01', 'PTS': 20, 'TEAM_ID': 1610612739}])
    monkeypatch.setattr(client, 'get_player_season_stats', lambda pid, season: {'PTS': 15.2})
    monkeypatch.setattr(client, 'get_advanced_player_stats', lambda pid, season: {'PER': 12.3})
    monkeypatch.setattr(client, 'get_player_season_stats_multi', lambda pid, seasons: {s: {'PTS': 15.0 + i} for i, s in enumerate(seasons)})
    monkeypatch.setattr(client, 'get_advanced_player_stats_multi', lambda pid, seasons: {'per_season': {s: {'PER': 10 + i} for i, s in enumerate(seasons)}, 'aggregated': {'PER': 11.0}})
    monkeypatch.setattr(client, 'get_team_stats_multi', lambda tid, seasons: {s: {'PTS_avg': 110 + i} for i, s in enumerate(seasons)})
    monkeypatch.setattr(client, 'get_advanced_team_stats_multi', lambda tid, seasons: {'per_season': {s: {'OFF_RATING': 105 + i} for i, s in enumerate(seasons)}, 'aggregated': {'OFF_RATING': 106.0}})

    ctx = svc.get_player_context_for_training('Player X', 'points', '2024-01-02', '2024-25')
    assert ctx['player'] == 'Player X'
    assert 'seasonStatsMulti' in ctx
    assert 'advancedStatsMulti' in ctx
    assert 'teamStatsMulti' in ctx
    assert 'teamAdvancedMulti' in ctx
