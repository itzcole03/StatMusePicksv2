import sys
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.nba_stats_client import find_player_id_by_name
from backend.services import training_data_service as tds

players = ['Trae Young', 'Jayson Tatum', 'Jalen Brunson']
seasons = ['2024-25']
for name in players:
    try:
        pid = find_player_id_by_name(name)
    except Exception as e:
        print(f"{name}: failed to resolve id: {e}")
        continue
    print(f"{name} -> pid={pid}")
    try:
        df = tds.generate_training_data(name, stat='points', min_games=1, fetch_limit=50, seasons=seasons, pid=int(pid))
        cnt = 0 if df is None else len(df)
        print(f"  generated rows: {cnt}")
        if df is not None:
            print(df[['player','game_date','target']].head().to_dict())
    except Exception as e:
        print(f"  generate_training_data error: {e}")
