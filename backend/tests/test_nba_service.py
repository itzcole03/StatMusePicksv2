from backend.services import nba_service


class DummyGame:
    def __init__(self, date, matchup, pts):
        self.GAME_DATE = date
        self.MATCHUP = matchup
        self.PTS = pts


def test_get_player_summary_happy_path(monkeypatch, tmp_path):
    # Mock redis client to ensure caching path works
    class FakeRedis:
        def __init__(self):
            self.store = {}

        def get(self, k):
            return self.store.get(k)

        def setex(self, k, ex, v):
            self.store[k] = v

    fake_rc = FakeRedis()
    monkeypatch.setattr(nba_service, "_redis_client", lambda: fake_rc)

    # Mock nba_stats_client functions
    monkeypatch.setattr(
        nba_service.nba_stats_client, "find_player_id_by_name", lambda name: 123
    )

    def fake_fetch(pid, limit, season=None):
        # return list of dict-like rows consistent with nba_api DataFrame->to_dict
        return [
            {"GAME_DATE": "2025-11-10", "MATCHUP": "TEAM A vs TEAM B", "PTS": 25},
            {"GAME_DATE": "2025-11-08", "MATCHUP": "TEAM A vs TEAM C", "PTS": 30},
        ]

    monkeypatch.setattr(nba_service.nba_stats_client, "fetch_recent_games", fake_fetch)

    out = nba_service.get_player_summary(
        "LeBron James", stat="points", limit=2, debug=True
    )
    assert out["player"] == "LeBron James"
    assert out["stat"] == "points"
    assert out["seasonAvg"] == 27.5
    assert out["recentGames"][0]["gameDate"] == "2025-11-10"
    # Ensure it wrote into fake redis
    key = f"player_summary:LeBron James:points:2:any"
    assert key in fake_rc.store


def test_build_external_context_for_projections_partial(monkeypatch):
    # Simulate missing player resolution
    monkeypatch.setattr(
        nba_service.nba_stats_client, "find_player_id_by_name", lambda name: None
    )

    inputs = [{"player": "Unknown Player"}, {"player": "Also Unknown"}]
    results = nba_service.build_external_context_for_projections(inputs)
    assert len(results) == 2
    assert results[0]["error"].lower().startswith("player") or results[0].get("error")
