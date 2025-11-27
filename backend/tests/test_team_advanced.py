from backend.services import nba_stats_client as nbc


def sample_team_games():
    # Minimal synthetic team game logs
    return [
        {
            "GAME_DATE": "2024-10-01",
            "PTS": 110,
            "OPP_PTS": 102,
            "FGA": 85,
            "FGM": 45,
            "FTA": 20,
            "FTM": 15,
        },
        {
            "GAME_DATE": "2024-10-03",
            "PTS": 120,
            "OPP_PTS": 115,
            "FGA": 90,
            "FGM": 50,
            "FTA": 25,
            "FTM": 18,
        },
        {
            "GAME_DATE": "2024-10-05",
            "PTS": 105,
            "OPP_PTS": 100,
            "FGA": 80,
            "FGM": 40,
            "FTA": 22,
            "FTM": 16,
        },
    ]


def test_team_advanced_fallback_monkeypatch(monkeypatch):
    # Monkeypatch fetch_team_games to return synthetic logs
    monkeypatch.setattr(
        nbc,
        "fetch_team_games",
        lambda team_id, limit=500, season=None: sample_team_games(),
    )

    stats = nbc.get_advanced_team_stats_fallback(1610612744, "2024-25")
    assert isinstance(stats, dict)
    assert stats.get("games") == 3
    assert "PTS_avg" in stats
    assert "FG_pct" in stats


def test_team_advanced_multi_aggregation(monkeypatch):
    # Return different synthetic sets per season
    def fake_fetch(team_id, limit=500, season=None):
        if season == "2024-25":
            return sample_team_games()
        else:
            return [
                {
                    "GAME_DATE": "2023-10-01",
                    "PTS": 112,
                    "OPP_PTS": 108,
                    "FGA": 86,
                    "FGM": 46,
                    "FTA": 21,
                    "FTM": 16,
                },
            ]

    monkeypatch.setattr(nbc, "fetch_team_games", fake_fetch)

    out = nbc.get_advanced_team_stats_multi(1610612744, ["2024-25", "2023-24"])
    assert "per_season" in out and "aggregated" in out
    assert "2024-25" in out["per_season"]
    assert "2023-24" in out["per_season"]
    agg = out["aggregated"]
    assert "games" in agg
