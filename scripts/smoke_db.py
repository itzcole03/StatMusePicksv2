"""Smoke test: initialize DB (if needed), insert sample rows, and verify queries.
This script uses the runtime `DATABASE_URL` env var if set; otherwise it uses local sqlite dev.db.

Run:
  $env:DATABASE_URL='postgresql+asyncpg://postgres:postgres@localhost:5432/statmuse_dev'
  python .\scripts\smoke_db.py
"""
import asyncio
import os
import sys
import datetime

from backend import db as backend_db
from backend.models import Player, Projection, Game, PlayerStat, Prediction


async def main():
    # Ensure engine/sessionmaker exists
    backend_db._ensure_engine_and_session()

    # Create tables (safe: Alembic preferred in prod)
    await backend_db.init_db()

    Session = backend_db.AsyncSessionLocal

    async with Session() as session:
        # Insert a sample player
        player = Player(name="Test Player", team="TST", position="PG")
        session.add(player)
        await session.flush()  # populate player.id

        # Insert a sample game (use timezone-aware UTC timestamp)
        game = Game(game_date=datetime.datetime.now(datetime.timezone.utc), home_team="TST", away_team="OPP")
        session.add(game)
        await session.flush()

        # Insert player stat
        stat = PlayerStat(player_id=player.id, game_id=game.id, stat_type="points", value=12.5)
        session.add(stat)

        # Insert a projection
        proj = Projection(player_id=player.id, source="smoke", stat="points", line=11.5)
        session.add(proj)

        # Insert a prediction
        pred = Prediction(player_id=player.id, stat_type="points", predicted_value=12.0, actual_value=None, game_id=game.id)
        session.add(pred)

        await session.commit()

    # Re-open session to query counts
    async with Session() as session:
        p_count = (await session.execute("select count(*) from players")).scalar()
        g_count = (await session.execute("select count(*) from games")).scalar()
        ps_count = (await session.execute("select count(*) from player_stats")).scalar()
        proj_count = (await session.execute("select count(*) from projections")).scalar()
        pred_count = (await session.execute("select count(*) from predictions")).scalar()

        print(f"players={p_count}, games={g_count}, player_stats={ps_count}, projections={proj_count}, predictions={pred_count}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print("Smoke DB test failed:", e)
        sys.exit(2)
    else:
        print("Smoke DB test completed successfully")
