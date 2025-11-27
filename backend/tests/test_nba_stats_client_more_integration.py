import os

import pytest

from backend.services import nba_stats_client as nbc

skip_cond = (nbc.players is None) or os.getenv("NBA_INTEGRATION", "") != "1"


@pytest.mark.skipif(
    skip_cond, reason="Requires nba_api installed and NBA_INTEGRATION=1"
)
def test_integration_team_and_career():
    # fetch teams list
    teams = nbc.fetch_all_teams()
    assert isinstance(teams, list)
    if not teams:
        pytest.skip("no teams available from nba_api")

    # pick a team and fetch recent games
    tid = teams[0].get("id") or teams[0].get("team_id")
    assert tid is not None
    games = nbc.fetch_team_games(tid, limit=3)
    assert isinstance(games, list)

    # pick a player from players list and fetch career/career-season stats
    players = nbc.fetch_all_players()
    assert isinstance(players, list)
    if players:
        pid = players[0].get("id") or players[0].get("player_id")
        if pid:
            stats = nbc.get_player_season_stats(pid, season=None)  # may return {}
            assert isinstance(stats, dict)
