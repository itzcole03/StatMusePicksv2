from __future__ import annotations
import sys
import traceback

print('PYTHON:', sys.executable)
try:
    from nba_api.stats.static import players as nba_players_static
    from nba_api.stats.endpoints import playergamelog
    print('nba_api import OK')
except Exception as e:
    print('nba_api import FAILED:', e)
    traceback.print_exc()
    sys.exit(1)

# Try to find player id for Stephen Curry
try:
    matches = nba_players_static.find_players_by_full_name('Stephen Curry')
    print('find_players_by_full_name result count:', len(matches))
    pid = None
    if matches:
        m = matches[0]
        pid = m.get('id') if isinstance(m, dict) else getattr(m, 'id', None)
    print('player id resolved:', pid)
except Exception as e:
    print('player lookup failed:', e)
    traceback.print_exc()
    pid = None

if not pid:
    print('No player id; aborting')
    sys.exit(2)

# Try a recent season fetch
season = '2024-25'
print('Attempting PlayerGameLog for player_id', pid, 'season', season)
try:
    pgl = playergamelog.PlayerGameLog(player_id=pid, season=season)
    dfs = pgl.get_data_frames()
    print('get_data_frames returned', len(dfs))
    if dfs:
        df = dfs[0]
        print('rows:', len(df))
        print('columns:', list(df.columns))
        print('first 3 rows:')
        print(df.head(3).to_dict(orient='records'))
    else:
        print('No dataframes returned')
except Exception as e:
    print('PlayerGameLog fetch failed:', e)
    traceback.print_exc()
    sys.exit(3)

print('probe completed successfully')