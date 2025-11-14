"""Helper script to list distinct stat_type values from player_stats.

Run from repository root with the venv activated or with PYTHONPATH set.
"""
import asyncio

from backend import db
from sqlalchemy import text


async def main():
    db._ensure_engine_and_session()
    async with db.engine.connect() as conn:
        res = await conn.execute(text("SELECT DISTINCT stat_type FROM player_stats"))
        # SQLAlchemy Async Result may return list-like from .all()/.fetchall();
        # use .all() which returns a list of Row objects and avoid awaiting it.
        result_rows = res.all()
        rows = [r[0] for r in result_rows]
        print(rows)


if __name__ == "__main__":
    asyncio.run(main())
