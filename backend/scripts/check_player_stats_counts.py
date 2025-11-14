"""Print player_stats counts per player (helper for shell usage).

Run with:
  & .\.venv\Scripts\Activate.ps1; python backend/scripts/check_player_stats_counts.py
"""
from backend import db
import asyncio
from sqlalchemy import text


async def main():
    db._ensure_engine_and_session()
    async with db.engine.connect() as conn:
        res = await conn.execute(text("SELECT p.name AS player, count(*) as cnt FROM player_stats ps JOIN players p ON ps.player_id=p.id GROUP BY p.name"))
        rows = res.fetchall()
        if not rows:
            print("No player_stats rows found.")
            return
        print("player_stats counts:")
        for r in rows:
            print(f"{r[0]}: {r[1]}")


if __name__ == "__main__":
    asyncio.run(main())
