from backend.services import nba_service


def test_get_player_summary_playercareerstats_fallback(monkeypatch):
    # Mock redis to be absent
    monkeypatch.setattr(nba_service, "_redis_client", lambda: None)

    # Mock player id resolution
    monkeypatch.setattr(
        nba_service.nba_stats_client, "find_player_id_by_name", lambda name: 999
    )

    # Return no recent games so code attempts playercareerstats path
    monkeypatch.setattr(
        nba_service.nba_stats_client,
        "fetch_recent_games",
        lambda pid, lim, season=None: [],
    )

    # Fake playercareerstats.PlayerCareerStats -> object with get_data_frames()
    class FakeDF:
        def __init__(self):
            self.empty = False
            self.columns = ["SEASON_ID"]

        def __getitem__(self, key):
            class Col:
                def tolist(self):
                    return ["2024-25"]

            return Col()

    class FakePCS:
        def __init__(self, player_id=None):
            pass

        def get_data_frames(self):
            return [FakeDF()]

    # Attach fake PlayerCareerStats to the nba_stats_client module
    monkeypatch.setattr(
        nba_service.nba_stats_client, "playercareerstats", mock := type("M", (), {})()
    )
    setattr(mock, "PlayerCareerStats", FakePCS)

    out = nba_service.get_player_summary(
        "Some Player", stat="points", limit=5, debug=False
    )
    assert out.get("lastSeason") == "2024-25"


def test_get_player_summary_redis_errors_fallback(monkeypatch):
    # Simulate redis client that raises on get and setex
    class BadRedis:
        def get(self, k):
            raise RuntimeError("redis get failed")

        def setex(self, k, ex, v):
            raise RuntimeError("redis setex failed")

    monkeypatch.setattr(nba_service, "_redis_client", lambda: BadRedis())

    # Mock nba_stats_client to return a simple recent list
    monkeypatch.setattr(
        nba_service.nba_stats_client, "find_player_id_by_name", lambda name: 321
    )
    monkeypatch.setattr(
        nba_service.nba_stats_client,
        "fetch_recent_games",
        lambda pid, lim, season=None: [
            {"GAME_DATE": "2025-10-01", "MATCHUP": "A vs B", "PTS": 10}
        ],
    )

    out = nba_service.get_player_summary(
        "Player X", stat="points", limit=1, debug=False
    )
    assert out["player"] == "Player X"
    # Ensure even though redis errors were raised, function returned data
    assert out.get("recentGames")
