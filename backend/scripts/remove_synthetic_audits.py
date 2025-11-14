"""Remove synthetic audit rows from the dev DB.

This script reads audit JSON files (default pattern `synth_fetch_*.json`) and
deletes any `player_stats` and `games` rows whose `game_id` matches the
integer surrogate used when the audits were upserted.

It will back up the SQLite DB file `dev.db` to `dev.db.bak` before making
destructive changes. Use with care.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
from pathlib import Path
from typing import List, Set

from sqlalchemy import text

from backend import db


def _compute_surrogate_id(gid_raw) -> int:
    """Match the surrogate computation used in `upsert_audits_to_db`.

    If gid_raw is numeric, return int(gid_raw). Otherwise return a stable
    32-bit positive integer derived from hash(gid_raw).
    """
    if gid_raw is None:
        return None
    try:
        return int(gid_raw)
    except Exception:
        return abs(hash(str(gid_raw))) % (10 ** 9)


def collect_ids_from_files(dirpath: Path, pattern: str) -> Set[int]:
    ids = set()
    for p in dirpath.glob(pattern):
        try:
            with open(p, "r", encoding="utf-8") as fh:
                rows = json.load(fh)
        except Exception:
            continue
        for r in rows:
            gid_raw = r.get("GAME_ID") or r.get("gameId") or r.get("game_id") or r.get("id")
            sid = _compute_surrogate_id(gid_raw)
            if sid is not None:
                ids.add(sid)
    return ids


async def _delete_ids(ids: List[int]):
    if not ids:
        print("No synthetic ids found; nothing to delete.")
        return

    db._ensure_engine_and_session()
    async with db.engine.begin() as conn:
        # Count how many player_stats and games would be deleted
        q_count_ps = text(f"SELECT COUNT(*) FROM player_stats WHERE game_id IN ({','.join([':id'+str(i) for i in range(len(ids))])})")
        params = {f"id{i}": v for i, v in enumerate(ids)}
        res = await conn.execute(q_count_ps, params)
        cnt_ps = res.scalar() or 0
        q_count_g = text(f"SELECT COUNT(*) FROM games WHERE id IN ({','.join([':id'+str(i) for i in range(len(ids))])})")
        res2 = await conn.execute(q_count_g, params)
        cnt_g = res2.scalar() or 0

        print(f"About to delete {cnt_ps} player_stats rows and {cnt_g} games rows for {len(ids)} synthetic ids.")
        # Perform deletions
        q_del_ps = text(f"DELETE FROM player_stats WHERE game_id IN ({','.join([':id'+str(i) for i in range(len(ids))])})")
        await conn.execute(q_del_ps, params)
        q_del_g = text(f"DELETE FROM games WHERE id IN ({','.join([':id'+str(i) for i in range(len(ids))])})")
        await conn.execute(q_del_g, params)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default="backend/ingest_audit")
    p.add_argument("--pattern", default="synth_fetch_*.json")
    p.add_argument("--backup", action="store_true", help="Backup dev.db to dev.db.bak before deleting")
    args = p.parse_args(argv)

    dirpath = Path(args.dir)
    if not dirpath.exists():
        print(f"Audit directory does not exist: {dirpath}")
        return 2

    ids = collect_ids_from_files(dirpath, args.pattern)
    if not ids:
        print("No synthetic audit ids found.")
        return 0

    # Backup SQLite DB if requested and file exists
    # DB file location default: ./dev.db
    dbfile = Path("./dev.db")
    if args.backup and dbfile.exists():
        bak = dbfile.with_suffix(".db.bak")
        print(f"Backing up {dbfile} -> {bak}")
        shutil.copy(dbfile, bak)

    print(f"Deleting {len(ids)} synthetic ids from DB...")
    asyncio.run(_delete_ids(list(ids)))
    print("Done.")


if __name__ == "__main__":
    main()
