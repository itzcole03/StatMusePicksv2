import pandas as pd

from backend.services import nba_stats_client as client


def test_get_team_stats_computes_additional_metrics(monkeypatch):
    # Fake TeamGameLog that returns three games with FGM/FGA and FTM/FTA
    class FakeTG:
        def __init__(self, team_id, **kwargs):
            self.team_id = team_id

        def get_data_frames(self):
            df = pd.DataFrame(
                [
                    {
                        "PTS": 100,
                        "OPP_PTS": 95,
                        "FGM": 36,
                        "FGA": 80,
                        "FTM": 20,
                        "FTA": 25,
                    },
                    {
                        "PTS": 110,
                        "OPP_PTS": 105,
                        "FGM": 40,
                        "FGA": 85,
                        "FTM": 22,
                        "FTA": 28,
                    },
                    {
                        "PTS": 105,
                        "OPP_PTS": 100,
                        "FGM": 38,
                        "FGA": 82,
                        "FTM": 18,
                        "FTA": 22,
                    },
                ]
            )
            return [df]

    monkeypatch.setattr(client, "teamgamelog", type("m", (), {"TeamGameLog": FakeTG}))
    monkeypatch.setattr(client, "_redis_client", lambda: None)

    # Clear in-process cache
    client._local_cache.clear()

    stats = client.get_team_stats(999)
    assert round(stats.get("PTS_avg", 0), 2) == round((100 + 110 + 105) / 3, 2)
    assert stats.get("games", 0) == 3
    # FG_pct = sum(FGM)/sum(FGA) = (36+40+38)/(80+85+82)
    expected_fg = (36 + 40 + 38) / (80 + 85 + 82)
    assert abs(stats.get("FG_pct", 0) - expected_fg) < 1e-6
    expected_ft = (20 + 22 + 18) / (25 + 28 + 22)
    assert abs(stats.get("FT_pct", 0) - expected_ft) < 1e-6
