from __future__ import annotations
from backend.scripts.populate_dev_db_from_nba import fetch_player_games, normalize_game_row, safe_name
from backend.services import nba_stats_client
try:
    from backend.services import nba_api_helper
except Exception:
    nba_api_helper = None

players = ['Stephen Curry','LeBron James','Kevin Durant']
for player in players:
    print('\n=== Player:', player)
    import asyncio
    games = asyncio.get_event_loop().run_until_complete(fetch_player_games(player, max_games=1000, deep=True, target_min_games=50, seasons_start=2005, seasons_end=2025))
    print('fetch_player_games returned', len(games))
    pid = nba_stats_client.find_player_id_by_name(player) or nba_stats_client.find_player_id(player)
    print('pid resolved by nba_stats_client:', pid)
    if pid and nba_api_helper:
        rows = nba_api_helper.fetch_career_games_by_id(pid, seasons_start=2005, seasons_end=2025)
        print('nba_api_helper returned', len(rows), 'rows')
        if rows:
            print('sample nba_api_helper row keys:', list(rows[0].keys()))
            print('sample nba_api_helper row (first):', {k: rows[0].get(k) for k in list(rows[0].keys())[:8]})
        # show a few gid variants from rows
        sample_row_gids = []
        for r in (rows or [])[:5]:
            sample_row_gids.append({k: r.get(k) for k in ('GAME_ID','Game_ID','gameId','game_id','id') if r.get(k) is not None})
        print('sample row gid candidates:', sample_row_gids)
        sample_game_gids = []
        for r in (games or [])[:5]:
            sample_game_gids.append({k: r.get(k) for k in ('GAME_ID','Game_ID','gameId','game_id','id') if r.get(k) is not None})
        print('sample games gid candidates:', sample_game_gids)
        combined = []
        seen = set()
        for r in (rows or []) + (games or []):
            gid = r.get('GAME_ID') or r.get('gameId') or r.get('game_id')
            if not gid:
                continue
            if gid in seen:
                continue
            seen.add(gid)
            combined.append(r)
        print('combined length', len(combined))
        norm = [normalize_game_row(g) for g in combined]
        print('normalized length', len(norm))
        if norm:
            print('sample normalized row:', norm[0])
    else:
        print('skipping nba_api_helper augmentation')
print('\ndone')
