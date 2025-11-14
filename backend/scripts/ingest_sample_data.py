"""Ingest sample projections and synthesize historical player_stats.

Reads `scripts/sample_projections.json` and inserts players, games,
projections, and a configurable number of synthetic player_stats rows
per player to allow dataset generation/testing.

Run with venv activated and PYTHONPATH set to repo root.
"""
import asyncio
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict

from sqlalchemy import text

from backend import db


SAMPLE_PATH = Path(__file__).parents[2] / "scripts" / "sample_projections.json"


async def upsert_player(conn, name: str, team: str):
    # find existing player
    res = await conn.execute(text("SELECT id FROM players WHERE name = :name"), {"name": name})
    row = res.first()
    if row:
        return row[0]
    await conn.execute(
        text("INSERT INTO players (name, team, created_at) VALUES (:name, :team, CURRENT_TIMESTAMP)"),
        {"name": name, "team": team},
    )
    res2 = await conn.execute(text("SELECT id FROM players WHERE name = :name"), {"name": name})
    return res2.first()[0]


async def insert_game(conn, game_date: datetime, home_team: str, away_team: str):
    # insert a game; if exists (same date + teams) return id
    res = await conn.execute(
        text("SELECT id FROM games WHERE game_date = :gd AND home_team = :home AND away_team = :away"),
        {"gd": game_date.isoformat(), "home": home_team, "away": away_team},
    )
    row = res.first()
    if row:
        return row[0]
    await conn.execute(
        text("INSERT INTO games (game_date, home_team, away_team, created_at) VALUES (:gd, :home, :away, CURRENT_TIMESTAMP)"),
        {"gd": game_date.isoformat(), "home": home_team, "away": away_team},
    )
    # fetch id
    res2 = await conn.execute(text("SELECT id FROM games WHERE game_date = :gd AND home_team = :home AND away_team = :away"), {"gd": game_date.isoformat(), "home": home_team, "away": away_team})
    return res2.first()[0]


async def insert_projection(conn, player_id: int, stat: str, line: float, projection_at: datetime, source: str = "sample"):
    await conn.execute(
        text(
            "INSERT INTO projections (player_id, source, stat, line, projection_at, created_at) VALUES (:pid, :src, :stat, :line, :pa, CURRENT_TIMESTAMP)"
        ),
        {"pid": player_id, "src": source, "stat": stat, "line": line, "pa": projection_at.isoformat()},
    )


async def insert_player_stat(conn, player_id: int, game_id: int, stat_type: str, value: float, created_at: datetime):
    await conn.execute(
        text("INSERT INTO player_stats (player_id, game_id, stat_type, value, created_at) VALUES (:pid, :gid, :st, :val, :ca)"),
        {"pid": player_id, "gid": game_id, "st": stat_type, "val": float(value), "ca": created_at.isoformat()},
    )


async def main(synth_games_per_player: int = 30):
    db._ensure_engine_and_session()
    data = json.loads(SAMPLE_PATH.read_text())
    async with db.engine.begin() as conn:
        for item in data:
            name = item.get("player")
            team = item.get("team") or "TBD"
            stat = item.get("stat")
            line = float(item.get("line"))
            start_time = datetime.fromisoformat(item.get("startTime"))

            player_id = await upsert_player(conn, name, team)
            # Insert a game for the projection start time
            game_id = await insert_game(conn, start_time, team, "OPP")
            await insert_projection(conn, player_id, stat, line, start_time)

            # Synthesize historical games: days back from start_time
            for i in range(1, synth_games_per_player + 1):
                # space games 2 days apart
                gd = start_time - timedelta(days=2 * i)
                gid = await insert_game(conn, gd, team, f"OPP{i}")
                # synthetic stat value: random around line with noise
                # use lower variance for earlier games and slightly trending
                noise = random.normalvariate(0, 5.0)
                value = max(0.0, line + noise - (i * 0.02))
                await insert_player_stat(conn, player_id, gid, stat, value, gd)


if __name__ == "__main__":
    # default: create 30 synthetic games per player so min-games=30 can be used
    asyncio.run(main(synth_games_per_player=30))
