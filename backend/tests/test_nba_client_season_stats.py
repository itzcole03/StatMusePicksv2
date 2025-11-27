import pandas as pd

from backend.services import nba_stats_client


def test_get_player_season_stats_from_playercareerstats(monkeypatch, tmp_path):
    # Build a small DataFrame that mimics playercareerstats output
    df = pd.DataFrame(
        [
            {"SEASON_ID": "2024-25", "PTS": 25, "AST": 8, "REB": 7},
            {"SEASON_ID": "2024-25", "PTS": 30, "AST": 9, "REB": 6},
            {"SEASON_ID": "2023-24", "PTS": 20, "AST": 5, "REB": 5},
        ]
    )

    class FakePCS:
        def __init__(self, player_id=None):
            pass

        def get_data_frames(self):
            return [df]

    # Attach fake playercareerstats module/class
    monkeypatch.setattr(
        nba_stats_client, "playercareerstats", mock := type("M", (), {})()
    )
    setattr(mock, "PlayerCareerStats", FakePCS)

    out = nba_stats_client.get_player_season_stats(12345, "2024-25")
    # Average PTS = (25+30)/2 = 27.5
    assert round(out.get("PTS", 0), 2) == 27.5
    assert round(out.get("AST", 0), 2) == 8.5
    assert round(out.get("REB", 0), 2) == 6.5
