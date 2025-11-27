import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.nba_stats_client import (
    fetch_recent_games_multi,
    find_player_id_by_name,
)

players = ["Trae Young", "Jayson Tatum", "Jalen Brunson"]
seasons = ["2024-25"]

for name in players:
    try:
        pid = find_player_id_by_name(name)
        print(f"{name} -> pid={pid}")
        games = (
            fetch_recent_games_multi(pid, seasons=seasons, limit_per_season=50) or []
        )
        print(f"  fetched {len(games)} games")
        for g in games[:5]:
            print(
                "   ",
                {
                    k: g.get(k)
                    for k in ["game_id", "game_date", "pts", "team", "opponent"]
                    if k in g
                },
            )
    except Exception as e:
        print(f"Error for {name}: {e}")
