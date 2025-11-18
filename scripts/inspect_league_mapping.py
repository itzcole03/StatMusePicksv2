#!/usr/bin/env python3
from backend.services import nba_stats_client
import json,sys,pprint

def main():
    try:
        m = nba_stats_client.fetch_season_league_player_game_logs('2024-25')
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
    if not m:
        print('EMPTY_MAPPING')
        return
    for k,v in list(m.items())[:1]:
        print('SAMPLED_PLAYER_ID:', k)
        print('NUM_GAMES:', len(v))
        pprint.pprint(v[:3])
        break

if __name__ == '__main__':
    main()
