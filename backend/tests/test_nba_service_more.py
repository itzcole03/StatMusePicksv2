import time

from backend.services import nba_service


def test_playercareerstats_empty_frames(monkeypatch):
    # No redis
    monkeypatch.setattr(nba_service, "_redis_client", lambda: None)

    # Resolve player id, but return no recent games so code hits playercareerstats
    monkeypatch.setattr(nba_service.nba_stats_client, "find_player_id_by_name", lambda name: 777)
    monkeypatch.setattr(nba_service.nba_stats_client, "fetch_recent_games", lambda pid, lim, season=None: [])

    class EmptyDF:
        def __init__(self):
            self.empty = True
            self.columns = []

    class FakePCS:
        def __init__(self, player_id=None):
            pass

        def get_data_frames(self):
            return [EmptyDF()]

    monkeypatch.setattr(nba_service.nba_stats_client, "playercareerstats", mock := type("M", (), {})())
    setattr(mock, "PlayerCareerStats", FakePCS)

    out = nba_service.get_player_summary("NoGames Player", stat="points", limit=3, debug=False)
    # When df is empty, lastSeason should remain None and function should still indicate noGamesThisSeason
    assert out.get("lastSeason") is None
    assert out.get("noGamesThisSeason") is True


def test_playercareerstats_raises_exception(monkeypatch):
    # No redis
    monkeypatch.setattr(nba_service, "_redis_client", lambda: None)

    monkeypatch.setattr(nba_service.nba_stats_client, "find_player_id_by_name", lambda name: 888)
    monkeypatch.setattr(nba_service.nba_stats_client, "fetch_recent_games", lambda pid, lim, season=None: [])

    # Make PlayerCareerStats constructor raise
    class BadPCS:
        def __init__(self, player_id=None):
            raise RuntimeError("pcs init failed")

    monkeypatch.setattr(nba_service.nba_stats_client, "playercareerstats", mock := type("M", (), {})())
    setattr(mock, "PlayerCareerStats", BadPCS)

    out = nba_service.get_player_summary("Exploding PCS", stat="rebounds", limit=4, debug=False)
    # Even when playercareerstats raises, function should return a best-effort summary
    assert out.get("player") == "Exploding PCS"
    assert out.get("noGamesThisSeason") is True
