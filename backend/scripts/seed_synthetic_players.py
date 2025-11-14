"""Seed synthetic players, games, and player_stats into the dev database.

This script is safe to re-run: it uses high id offsets and ON CONFLICT DO NOTHING
to avoid clobbering existing rows. It's intended for local dev only.

Usage (PowerShell):
    & .venv\Scripts\Activate.ps1
    $env:DATABASE_URL = 'postgresql+asyncpg://postgres:postgres@localhost:5432/statmuse_dev'
    python backend/scripts/seed_synthetic_players.py --players 10 --games 60
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import text

from backend import db


async def seed(num_players: int = 10, games_per_player: int = 60, stat_type: str = "points"):
    db._ensure_engine_and_session()

    async with db.engine.begin() as conn:
        # Determine safe id offsets to avoid collisions with existing rows
        res = await conn.execute(text("SELECT COALESCE(MAX(id), 0) FROM players"))
        rows = res.all()
        max_pid = rows[0][0] if rows else 0
        start_pid = max_pid + 1000

        res = await conn.execute(text("SELECT COALESCE(MAX(id), 0) FROM games"))
        rows = res.all()
        max_gid = rows[0][0] if rows else 0
        start_gid = max_gid + 100000

        inserted_players = []
        for i in range(num_players):
            pid = start_pid + i + 1
            name = f"Synth Player {pid}"
            team = f"T{(i%30)+1:02d}"
            position = None
            await conn.execute(
                text(
                    "INSERT INTO players (id, name, team, position) VALUES (:id, :name, :team, :pos) ON CONFLICT (id) DO NOTHING"
                ),
                {"id": pid, "name": name, "team": team, "pos": position},
            )
            inserted_players.append((pid, name))

        # Create a pool of games (shared across players) with descending dates
        base_date = datetime.now(timezone.utc)
        game_ids = []
        total_games = games_per_player
        for gidx in range(total_games):
            gid = start_gid + gidx + 1
            gdate = base_date - timedelta(days=2 * gidx)
            home = f"T{(gidx%30)+1:02d}"
            away = f"OPP{gidx}"
            await conn.execute(
                text(
                    "INSERT INTO games (id, game_date, home_team, away_team) VALUES (:id, :gd, :home, :away) ON CONFLICT (id) DO NOTHING"
                ),
                {"id": gid, "gd": gdate, "home": home, "away": away},
            )
            game_ids.append((gid, gdate))

        # Insert player_stats for each player across the game pool
        stats_inserted = 0
        for pid, _ in inserted_players:
            # spread player appearances across the games list
            for j, (gid, gdate) in enumerate(game_ids):
                # simple synthetic stat value pattern
                value = float(10 + (j % 30) + (pid % 5))
                await conn.execute(
                    text(
                        "INSERT INTO player_stats (player_id, game_id, stat_type, value) VALUES (:pid, :gid, :stype, :val)"
                    ),
                    {"pid": pid, "gid": gid, "stype": stat_type, "val": value},
                )
                stats_inserted += 1

    return {"players": len(inserted_players), "games": len(game_ids), "player_stats": stats_inserted}


def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--players", type=int, default=10)
    p.add_argument("--games", type=int, default=60)
    p.add_argument("--stat", type=str, default="points")
    return p.parse_args()


def main():
    args = _parse_args()
    out = asyncio.run(seed(num_players=args.players, games_per_player=args.games, stat_type=args.stat))
    print(f"Inserted: players={out['players']} games={out['games']} player_stats={out['player_stats']}")


if __name__ == "__main__":
    main()
