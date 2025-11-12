import json
import types
import pytest

from unittest import mock


def make_redis_stub(store=None):
    store = store or {}

    class Stub:
        def get(self, k):
            return store.get(k)

        def setex(self, k, ttl, v):
            store[k] = v

    return Stub()


import pytest


def test_find_player_id_by_name_no_nba_api(monkeypatch):
    # Ensure graceful fallback when nba_api isn't installed
    import importlib

    # Temporarily remove nba_api imports used in module
    monkeypatch.setitem(importlib.sys.modules, 'nba_api', None)

    from backend.services import nba_stats_client as ns

    # When nba_api not available, should return None for unknown names
    assert ns.find_player_id_by_name('Nonexistent Player') is None


def test_find_player_id_by_name_with_players(monkeypatch):
    # Mock players.find_players_by_full_name
    mock_players = types.SimpleNamespace()

    def find_players_by_full_name(n):
        return [{'id': 12345, 'full_name': n}]

    mock_players.find_players_by_full_name = find_players_by_full_name
    mock_players.get_players = lambda: [{'id': 12345, 'full_name': 'John Doe'}]

    monkeypatch.setattr('backend.services.nba_stats_client.players', mock_players, raising=False)

    # Stub redis client
    monkeypatch.setattr('backend.services.nba_stats_client._redis_client', lambda: make_redis_stub())

    from backend.services import nba_stats_client as ns

    pid = ns.find_player_id_by_name('John Doe')
    assert pid == 12345


def test_fetch_recent_games_no_api(monkeypatch):
    # When nba_api endpoints missing, should return empty list
    monkeypatch.setattr('backend.services.nba_stats_client.playergamelog', None)

    from backend.services import nba_stats_client as ns

    assert ns.fetch_recent_games(None) == []
    assert ns.fetch_recent_games(0) == []


def test_fetch_recent_games_with_api(monkeypatch):
    # Mock PlayerGameLog behavior
    class FakeDF:
        def __init__(self, rows):
            self._rows = rows

        def head(self, n):
            return FakeDF(self._rows[:n])

        def to_dict(self, orient='records'):
            return self._rows

    class FakePGL:
        def __init__(self, player_id=None):
            self._player_id = player_id

        def get_data_frames(self):
            rows = [{'game_id': 1, 'PTS': 10}, {'game_id': 2, 'PTS': 20}]
            return [FakeDF(rows)]

    monkeypatch.setattr('backend.services.nba_stats_client.playergamelog', types.SimpleNamespace(PlayerGameLog=FakePGL))
    monkeypatch.setattr('backend.services.nba_stats_client._redis_client', lambda: make_redis_stub())

    from backend.services import nba_stats_client as ns

    res = ns.fetch_recent_games(999, limit=1)
    assert isinstance(res, list)
    assert len(res) == 1
    assert res[0]['PTS'] == 10


def test_get_player_season_stats_no_api(monkeypatch):
    monkeypatch.setattr('backend.services.nba_stats_client.playercareerstats', None)
    from backend.services import nba_stats_client as ns

    assert ns.get_player_season_stats(None, None) == {}
    assert ns.get_player_season_stats(0, '') == {}


@pytest.mark.unit
def test_marker_present():
    # Quick sanity test to ensure unit marker is discoverable
    assert True

