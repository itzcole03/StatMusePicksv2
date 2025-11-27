import pandas as pd


def test_generate_training_data_handles_empty_season_stats(monkeypatch):
    from backend.services import training_data_service as tds

    # Resolve player id
    monkeypatch.setattr(
        "backend.services.training_data_service.nba_stats_client.find_player_id_by_name",
        lambda name: 7,
    )

    # Provide sufficient games
    def fake_fetch_multi(pid, seasons=None, limit_per_season=500):
        out = []
        for i in range(30):
            out.append({"GAME_DATE": f"2024-01-{i+1:02d}", "PTS": 10 + i})
        return out

    monkeypatch.setattr(
        "backend.services.training_data_service.nba_stats_client.fetch_recent_games_multi",
        fake_fetch_multi,
    )

    # Advanced aggregated returns empty aggregated dict
    monkeypatch.setattr(
        "backend.services.training_data_service.nba_stats_client.get_advanced_player_stats_multi",
        lambda pid, seasons: {"per_season": {}, "aggregated": {}},
    )
    # Season stats multi empty or missing PTS
    monkeypatch.setattr(
        "backend.services.training_data_service.nba_stats_client.get_player_season_stats_multi",
        lambda pid, seasons: {s: {} for s in seasons},
    )

    df = tds.generate_training_data(
        "Edge Player",
        stat="points",
        min_games=10,
        fetch_limit=500,
        seasons=["2023-24", "2022-23"],
    )
    assert isinstance(df, pd.DataFrame)
    # Aggregated advanced fields should exist and be zero when missing
    assert "multi_PER" in df.columns and all(df["multi_PER"] == 0.0)
    assert "multi_TS_PCT" in df.columns and all(df["multi_TS_PCT"] == 0.0)
    # season avg should default to 0.0 when no PTS present
    assert "multi_season_PTS_avg" in df.columns and all(
        df["multi_season_PTS_avg"] == 0.0
    )


def test_get_team_stats_missing_fg_ft_columns(monkeypatch):
    from backend.services import nba_stats_client as client

    class FakeTG:
        def __init__(self, team_id, **kwargs):
            self.team_id = team_id

        def get_data_frames(self):
            # DataFrame has only PTS and OPP_PTS, no FGM/FGA/FTM/FTA
            df = pd.DataFrame(
                [
                    {"PTS": 100, "OPP_PTS": 95},
                    {"PTS": 110, "OPP_PTS": 105},
                ]
            )
            return [df]

    monkeypatch.setattr(client, "teamgamelog", type("m", (), {"TeamGameLog": FakeTG}))
    monkeypatch.setattr(client, "_redis_client", lambda: None)
    client._local_cache.clear()

    stats = client.get_team_stats(321)
    # PTS averages computed
    assert round(stats.get("PTS_avg", 0), 2) == 105.0
    # FG_pct and FT_pct should not be present when columns missing
    assert "FG_pct" not in stats
    assert "FT_pct" not in stats
