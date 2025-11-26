def make_redis_stub(store=None):
    store = store or {}

    class Stub:
        def get(self, k):
            return store.get(k)

        def setex(self, k, ttl, v):
            store[k] = v

    return Stub()


def test_fetch_recent_games_multi_aggregates(monkeypatch):
    # Provide season-specific game lists and ensure aggregation and sorting
    from backend.services import nba_stats_client as ns

    def fake_fetch(pid, lim, season=None):
        if season == "2023-24":
            return [
                {"GAME_DATE": "2024-04-10", "PTS": 10},
                {"GAME_DATE": "2024-03-01", "PTS": 12},
            ]
        if season == "2022-23":
            return [{"GAME_DATE": "2023-12-01", "PTS": 8}]
        return []

    monkeypatch.setattr(ns, "fetch_recent_games", fake_fetch)
    monkeypatch.setattr(ns, "_redis_client", lambda: make_redis_stub())

    res = ns.fetch_recent_games_multi(
        1, seasons=["2023-24", "2022-23"], limit_per_season=10
    )
    assert isinstance(res, list)
    # Expect three games aggregated
    assert len(res) == 3
    # Newest first by GAME_DATE
    assert res[0]["GAME_DATE"] == "2024-04-10"


def test_get_advanced_player_stats_multi_aggregates(monkeypatch):
    from backend.services import nba_stats_client as ns

    # Mock single-season advanced stats
    monkeypatch.setattr(
        ns,
        "get_advanced_player_stats",
        lambda pid, s: {"PER": 15.0} if s == "2023-24" else {"PER": 13.0},
    )
    monkeypatch.setattr(ns, "_redis_client", lambda: make_redis_stub())

    out = ns.get_advanced_player_stats_multi(10, ["2023-24", "2022-23"])
    assert "per_season" in out and "aggregated" in out
    assert out["per_season"]["2023-24"]["PER"] == 15.0
    # Aggregated PER should be mean of 15 and 13 -> 14.0
    assert abs(out["aggregated"].get("PER", 0) - 14.0) < 1e-6


def test_get_player_context_for_training_includes_multi(monkeypatch):
    from backend.services import nba_service as ns

    # Stub underlying client functions
    monkeypatch.setattr(
        "backend.services.nba_service.nba_stats_client.find_player_id_by_name",
        lambda name: 555,
    )
    monkeypatch.setattr(
        "backend.services.nba_service.nba_stats_client.fetch_recent_games",
        lambda pid, lim, season=None: [{"GAME_DATE": "2024-04-01", "TEAM_ID": 30}],
    )
    monkeypatch.setattr(
        "backend.services.nba_service.nba_stats_client.get_player_season_stats",
        lambda pid, s: {"PTS": 20.0},
    )
    monkeypatch.setattr(
        "backend.services.nba_service.nba_stats_client.get_advanced_player_stats",
        lambda pid, s: {"PER": 16.0},
    )
    monkeypatch.setattr(
        "backend.services.nba_service.nba_stats_client.get_player_season_stats_multi",
        lambda pid, seasons: {s: {"PTS": 18.0} for s in seasons},
    )
    monkeypatch.setattr(
        "backend.services.nba_service.nba_stats_client.get_advanced_player_stats_multi",
        lambda pid, seasons: {
            "per_season": {s: {"PER": 15.0} for s in seasons},
            "aggregated": {"PER": 15.0},
        },
    )
    monkeypatch.setattr(
        "backend.services.nba_service.nba_stats_client.get_team_stats_multi",
        lambda tid, seasons: {s: {"PTS_avg": 110.0} for s in seasons},
    )
    monkeypatch.setattr(
        "backend.services.nba_service._redis_client", lambda: make_redis_stub()
    )

    ctx = ns.get_player_context_for_training(
        "Some Player", "points", "2024-04-10", "2023-24"
    )
    assert ctx["playerId"] == 555
    assert "seasonsConsidered" in ctx and "2023-24" in ctx["seasonsConsidered"]
    assert "advancedStatsMulti" in ctx and "aggregated" in ctx["advancedStatsMulti"]
