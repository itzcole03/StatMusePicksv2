"""Remove synthetic audit rows by matching audit filename player -> `players.name`.

This script:
- Parses `backend/ingest_audit/synth_fetch_*.json` files.
- Extracts all `GAME_DATE` values per file.
- Infers a player name from the filename (e.g. `synth_fetch_Stephen_Curry.json` -> `Stephen Curry`).
- Finds internal `players.id` rows matching that name (case-insensitive) and deletes
  `player_stats` rows for that player where the game's date matches any of the audit dates.
- Removes any `games` rows that become orphaned after deleting `player_stats`.

Always run with `--backup` initially. This is conservative and auditable.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set

from sqlalchemy import text

from backend import db


def collect_dates_by_file(dirpath: Path, pattern: str) -> Dict[Path, Set[str]]:
    out: Dict[Path, Set[str]] = {}
    for p in dirpath.glob(pattern):
        try:
            with open(p, "r", encoding="utf-8") as fh:
                rows = json.load(fh)
        except Exception:
            continue
        dates = set()
        for r in rows:
            gdate = r.get("GAME_DATE") or r.get("game_date")
            if not gdate:
                continue
            ds = str(gdate)
            if 'T' in ds:
                ds = ds.split('T')[0]
            dates.add(ds)
        if dates:
            out[p] = dates
    return out


def filename_to_name(p: Path) -> str:
    # expected: synth_fetch_First_Last.json
    stem = p.stem
    if stem.startswith("synth_fetch_"):
        name = stem[len("synth_fetch_"):]
        # replace underscores with spaces
        return name.replace("_", " ")
    return stem.replace("_", " ")


async def _delete_for_files(files_dates: Dict[Path, Set[str]]):
    if not files_dates:
        print("No synth audit files with dates found; nothing to delete.")
        return

    db._ensure_engine_and_session()
    total_deleted_ps = 0
    total_deleted_games = 0

    async with db.engine.begin() as conn:
        # For each file, map filename->internal player ids by name
        for p, dates in files_dates.items():
            player_name = filename_to_name(p)
            # Find player internal ids with matching name (case-insensitive)
            q_players = text("SELECT id, name FROM players WHERE LOWER(name) = LOWER(:nm)")
            res = await conn.execute(q_players, {"nm": player_name})
            rows = res.mappings().all()
            if not rows:
                print(f"No players found matching name '{player_name}' (from {p.name})")
                continue
            internal_ids = [r["id"] for r in rows]

            for pid in internal_ids:
                # For each date, find game ids with that date
                for d in sorted(dates):
                    q_game_ids = text("SELECT id FROM games WHERE DATE(game_date) = :gdate")
                    resg = await conn.execute(q_game_ids, {"gdate": d})
                    game_ids = [r[0] for r in resg.fetchall()]
                    if not game_ids:
                        continue

                    # Delete player_stats for this player & game ids
                    q_count = text(f"SELECT COUNT(*) FROM player_stats WHERE player_id = :pid AND game_id IN ({','.join([':gid'+str(i) for i in range(len(game_ids))])})")
                    params = {"pid": pid}
                    params.update({f"gid{i}": v for i, v in enumerate(game_ids)})
                    cres = await conn.execute(q_count, params)
                    cnt = cres.scalar() or 0
                    if cnt > 0:
                        q_del = text(f"DELETE FROM player_stats WHERE player_id = :pid AND game_id IN ({','.join([':gid'+str(i) for i in range(len(game_ids))])})")
                        await conn.execute(q_del, params)
                        total_deleted_ps += cnt

                    # Remove orphaned games
                    for gid in game_ids:
                        q_del_game = text("DELETE FROM games WHERE id = :gid AND NOT EXISTS (SELECT 1 FROM player_stats WHERE game_id = :gid)")
                        await conn.execute(q_del_game, {"gid": gid})
                        q_check = text("SELECT COUNT(*) FROM games WHERE id = :gid")
                        rc = await conn.execute(q_check, {"gid": gid})
                        still = rc.scalar() or 0
                        if still == 0:
                            total_deleted_games += 1

    print(f"Deleted {total_deleted_ps} player_stats rows and {total_deleted_games} orphaned games rows.")


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default="backend/ingest_audit")
    p.add_argument("--pattern", default="synth_fetch_*.json")
    p.add_argument("--backup", action="store_true", help="Backup dev.db to timestamped file before deleting")
    args = p.parse_args(argv)

    dirpath = Path(args.dir)
    if not dirpath.exists():
        print(f"Audit directory does not exist: {dirpath}")
        return 2

    files_dates = collect_dates_by_file(dirpath, args.pattern)
    if not files_dates:
        print("No synth audit files with dates found.")
        return 0

    dbfile = Path("./dev.db")
    if args.backup and dbfile.exists():
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        bak = dbfile.with_name(f"dev.db.{ts}.bak")
        print(f"Backing up {dbfile} -> {bak}")
        shutil.copy(dbfile, bak)

    print(f"Deleting entries for {len(files_dates)} synth files...")
    asyncio.run(_delete_for_files(files_dates))
    print("Done.")


if __name__ == '__main__':
    main()
