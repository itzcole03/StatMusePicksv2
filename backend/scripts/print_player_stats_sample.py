"""Print sample player_stats rows for a player name.

Usage:
  python backend/scripts/print_player_stats_sample.py --player "Stephen Curry" --limit 20
"""
from __future__ import annotations

import argparse
import asyncio
from sqlalchemy import text
from backend import db


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--player", required=True)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    db._ensure_engine_and_session()
    async with db.engine.connect() as conn:
        q = text(
            "SELECT p.name as player, p.id as player_id, ps.game_id, ps.stat_type, ps.value, g.game_date FROM player_stats ps JOIN players p ON ps.player_id=p.id LEFT JOIN games g ON ps.game_id=g.id WHERE p.name = :name LIMIT :limit"
        )
        res = await conn.execute(q, {"name": args.player, "limit": args.limit})
        rows = res.fetchall()
        if not rows:
            print("No rows for player", args.player)
            return
        for r in rows:
            print(r)


if __name__ == "__main__":
    asyncio.run(main())
