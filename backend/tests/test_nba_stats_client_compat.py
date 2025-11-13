from backend.services import nba_stats_client


def test_nba_stats_client_exports_compatibility():
    # Ensure both new and legacy API names are present to avoid runtime errors
    assert hasattr(nba_stats_client, 'find_player_id_by_name')
    assert hasattr(nba_stats_client, 'find_player_id')
    assert hasattr(nba_stats_client, 'fetch_recent_games')
    assert hasattr(nba_stats_client, 'fetch_recent_games_by_id')
    assert hasattr(nba_stats_client, 'fetch_recent_games_by_name')
