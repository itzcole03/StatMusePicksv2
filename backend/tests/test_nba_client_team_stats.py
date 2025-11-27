import pandas as pd

from backend.services import nba_stats_client as client


def test_get_team_stats_computes_averages_and_caches(monkeypatch):
    # Fake TeamGameLog that returns two games
    class FakeTG:
        def __init__(self, team_id, **kwargs):
            self.team_id = team_id

        def get_data_frames(self):
            df = pd.DataFrame(
                [
                    {"PTS": 100, "OPP_PTS": 95},
                    {"PTS": 110, "OPP_PTS": 105},
                ]
            )
            return [df]

    # Patch the imported teamgamelog with our fake
    monkeypatch.setattr(client, "teamgamelog", type("m", (), {"TeamGameLog": FakeTG}))
    # Disable redis in tests by returning None
    monkeypatch.setattr(client, "_redis_client", lambda: None)

    # Clear in-process cache
    client._local_cache.clear()

    stats = client.get_team_stats(123)
    assert round(stats.get("PTS_avg", 0), 2) == 105.0
    assert round(stats.get("OPP_PTS_avg", 0), 2) == 100.0
    assert round(stats.get("PTS_diff", 0), 2) == 5.0

    # Now replace TeamGameLog with one that would raise if called (to ensure cache used)
    class BadTG:
        def __init__(self, team_id):
            raise RuntimeError("should not be called")

    monkeypatch.setattr(client, "teamgamelog", type("m", (), {"TeamGameLog": BadTG}))

    # Second call should return cached result and not raise
    stats2 = client.get_team_stats(123)
    assert stats2 == stats
