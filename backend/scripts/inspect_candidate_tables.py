"""Inspect candidate DB tables and print sample rows.

Run from repo root with venv activated and PYTHONPATH set.
"""
import asyncio
from backend import db
from sqlalchemy import text


async def main():
    db._ensure_engine_and_session()
    async with db.engine.connect() as conn:
        # List tables
        res = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = [r[0] for r in res.fetchall()]
        print('Tables in DB:', tables)

        candidates = ['projections', 'player_stats', 'players', 'player_map']
        for t in candidates:
            if t in tables:
                print('\n--- Sample rows from', t, '---')
                r = await conn.execute(text(f"SELECT * FROM {t} LIMIT 5"))
                rows = r.fetchall()
                for row in rows:
                    try:
                        print(dict(row._mapping))
                    except Exception:
                        print(row)
            else:
                print('\n(table not present):', t)


if __name__ == '__main__':
    asyncio.run(main())
