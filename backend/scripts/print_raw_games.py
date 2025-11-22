import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.nba_stats_client import find_player_id_by_name, fetch_recent_games_multi

name='Trae Young'
seasons=['2024-25']
pid=find_player_id_by_name(name)
print('pid', pid)
games = fetch_recent_games_multi(pid, seasons=seasons, limit_per_season=5)
print('games count', len(games))
for i,g in enumerate(games[:5]):
    print('--- game', i, 'repr ---')
    try:
        print(repr(g))
    except Exception:
        print(str(g))
    try:
        print('keys:', list(g.keys()))
    except Exception:
        print('not a dict')
    print('\n')
