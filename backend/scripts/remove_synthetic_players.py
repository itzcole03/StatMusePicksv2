"""Remove synthetic seeded players and their player_stats from the dev DB.

This helper is safe to run multiple times and only targets rows where
the player name matches the `Synth Player %` pattern inserted by
`seed_synthetic_players.py`.

Usage (PowerShell):

```pwsh
& .venv\Scripts\Activate.ps1
$env:DATABASE_URL = 'postgresql+asyncpg://postgres:postgres@localhost:5432/statmuse_dev'
python backend/scripts/remove_synthetic_players.py --yes
```

By default the script prompts for confirmation unless `--yes` is passed.
It performs the deletions in a single transaction and prints a summary.
"""
from __future__ import annotations

import argparse
import asyncio
from typing import List
from sqlalchemy import text
from backend import db


async def remove_synthetic(confirm: bool = True) -> dict:
    db._ensure_engine_and_session()
    async with db.engine.begin() as conn:
        # Find player ids matching the synthetic pattern
        res = await conn.execute(text("SELECT id FROM players WHERE name LIKE 'Synth Player %'"))
        rows = res.all()
        player_ids = [r[0] for r in rows]
        if not player_ids:
            return {"players_deleted": 0, "player_stats_deleted": 0}

        if confirm:
            print(f"Found {len(player_ids)} synthetic players to delete: {player_ids[:10]}{'...' if len(player_ids)>10 else ''}")
            ok = input("Proceed to delete these players and associated player_stats? [y/N]: ")
            if ok.lower() not in ("y", "yes"):
                print("Aborted by user.")
                return {"players_deleted": 0, "player_stats_deleted": 0}

        # Delete player_stats then players
        del_stats = await conn.execute(
            text("DELETE FROM player_stats WHERE player_id = ANY(:pids) RETURNING COUNT(*)"),
            {"pids": player_ids},
        )
        # SQLAlchemy's RETURNING COUNT(*) may not return a nice scalar across DBs; issue a simple count instead
        stats_count = await conn.execute(text("SELECT COUNT(*) FROM player_stats WHERE player_id = ANY(:pids)"), {"pids": player_ids})
        # Now delete the player rows
        await conn.execute(text("DELETE FROM player_stats WHERE player_id = ANY(:pids)"), {"pids": player_ids})
        p_del = await conn.execute(text("DELETE FROM players WHERE id = ANY(:pids) RETURNING COUNT(*)"), {"pids": player_ids})
        # derive counts
        stats_ct = int(stats_count.all()[0][0]) if stats_count is not None and stats_count.all() else 0
        players_ct = len(player_ids)
        return {"players_deleted": players_ct, "player_stats_deleted": stats_ct}


def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    return p.parse_args()


def main():
    args = _parse_args()
    out = asyncio.run(remove_synthetic(confirm=not args.yes))
    print(f"Result: players_deleted={out['players_deleted']} player_stats_deleted={out['player_stats_deleted']}")


if __name__ == "__main__":
    main()
