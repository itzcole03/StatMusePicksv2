from __future__ import annotations
import sys
from backend.services import nba_stats_client
try:
    from backend.services import nba_api_helper
except Exception as e:
    nba_api_helper = None
    print('nba_api_helper import failed', e)

players = ['Stephen Curry','LeBron James','Kevin Durant']
for p in players:
    pid = nba_stats_client.find_player_id_by_name(p) or nba_stats_client.find_player_id(p)
    print('player', p, '=> pid', pid)
    if pid and nba_api_helper:
        rows = nba_api_helper.fetch_career_games_by_id(pid, seasons_start=2005, seasons_end=2025)
        print('nba_api_helper returned', len(rows), 'rows for', p)
    else:
        print('skipping nba_api_helper call for', p)
print('done')
