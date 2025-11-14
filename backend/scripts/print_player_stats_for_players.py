"""Print sample player_stats rows for given internal player ids.

Usage: python backend/scripts/print_player_stats_for_players.py --players 2,3,13 --limit 50
"""
import argparse
import sqlite3
from typing import List


def parse_players(s: str) -> List[int]:
    return [int(x) for x in s.split(",") if x.strip()]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--players", default="2,3,13", help="Comma-separated internal player ids")
    p.add_argument("--limit", type=int, default=50)
    args = p.parse_args()

    players = parse_players(args.players)
    conn = sqlite3.connect("dev.db")
    cur = conn.cursor()

    placeholders = ",".join(["?" for _ in players])
    q = f"""
SELECT ps.id, ps.player_id, p.name, ps.game_id, g.game_date, ps.stat_type, ps.value
FROM player_stats ps
JOIN players p ON p.id = ps.player_id
LEFT JOIN games g ON g.id = ps.game_id
WHERE ps.player_id IN ({placeholders})
ORDER BY g.game_date DESC
LIMIT ?
"""
    params = players + [args.limit]
    cur.execute(q, params)
    rows = cur.fetchall()
    if not rows:
        print("No player_stats rows found for the requested player ids.")
        return

    print(f"Printing up to {args.limit} player_stats rows for players: {players}\n")
    for r in rows:
        print(r)

    # print counts per player
    print("\nCounts per player:")
    for pid in players:
        cur.execute("SELECT COUNT(*) FROM player_stats WHERE player_id = ?", (pid,))
        cnt = cur.fetchone()[0]
        print(f"player_id={pid}: {cnt}")

    conn.close()


if __name__ == '__main__':
    main()
