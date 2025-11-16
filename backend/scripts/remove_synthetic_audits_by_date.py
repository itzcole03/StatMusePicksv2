"""Remove synthetic audit rows by matching PLAYER_ID (nba id) and GAME_DATE.

This is safer than relying on surrogate game ids. It:
- Backs up `./dev.db` to a timestamped backup when `--backup` is supplied.
- Parses audit JSON files (default `backend/ingest_audit/synth_fetch_*.json`).
- For each unique (PLAYER_ID, GAME_DATE) tuple it deletes matching
  `player_stats` rows and then removes `games` rows that have no remaining
  `player_stats`.

Always run with `--backup` the first time.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Tuple

from sqlalchemy import text

from backend import db


def collect_player_date_pairs(dirpath: Path, pattern: str) -> Set[Tuple[int, str]]:
    pairs = set()
    for p in dirpath.glob(pattern):
        try:
            with open(p, "r", encoding="utf-8") as fh:
                rows = json.load(fh)
        except Exception:
            continue
        for r in rows:
            # audit shape uses PLAYER_ID and GAME_DATE
            pid = r.get("PLAYER_ID") or r.get("player_id") or r.get("PLAYER") or r.get("player")
            gdate = r.get("GAME_DATE") or r.get("game_date") or r.get("GAME_DATE_UTC")
            if pid is None or gdate is None:
                continue
            # Normalize date to YYYY-MM-DD
            try:
                ds = str(gdate)
                # If the audit provides a full datetime, take date-part
                if 'T' in ds:
                    ds = ds.split('T')[0]
                pairs.add((int(pid), ds))
            except Exception:
                continue
    return pairs


async def _delete_pairs(pairs: Set[Tuple[int, str]]):
    if not pairs:
        print("No synthetic (player, date) pairs found; nothing to delete.")
        return

    db._ensure_engine_and_session()
    summary = defaultdict(int)
    async with db.engine.begin() as conn:
        # Map nba_player_id -> internal player.id
        nba_ids = sorted({p for p, _ in pairs})
        q_players = text(f"SELECT id, nba_player_id FROM players WHERE nba_player_id IN ({','.join([':nid'+str(i) for i in range(len(nba_ids))])})")
        params = {f"nid{i}": v for i, v in enumerate(nba_ids)}
        res = await conn.execute(q_players, params)
        map_internal = {row['nba_player_id']: row['id'] for row in res.mappings().all()}  # nba_player_id -> id

        missing = [nid for nid in nba_ids if nid not in map_internal]
        if missing:
            print(f"Warning: {len(missing)} nba_player_id(s) from audits not found in players table: {missing}")

        # Group by player internal id -> list of dates
        grouped: Dict[int, List[str]] = defaultdict(list)
        for nba_pid, gdate in pairs:
            if nba_pid in map_internal:
                grouped[map_internal[nba_pid]].append(gdate)

        total_deleted_ps = 0
        total_deleted_games = 0

        for internal_pid, dates in grouped.items():
            unique_dates = sorted(set(dates))
            for d in unique_dates:
                # Find games matching date (date-part)
                q_game_ids = text("SELECT id FROM games WHERE DATE(game_date) = :gdate")
                resg = await conn.execute(q_game_ids, {"gdate": d})
                game_ids = [row[0] for row in resg.fetchall()]
                if not game_ids:
                    continue

                # Count player_stats matching this player+game(s)
                q_count = text(f"SELECT COUNT(*) FROM player_stats WHERE player_id = :pid AND game_id IN ({','.join([':gid'+str(i) for i in range(len(game_ids))])})")
                params = {"pid": internal_pid}
                params.update({f"gid{i}": v for i, v in enumerate(game_ids)})
                cres = await conn.execute(q_count, params)
                cnt = cres.scalar() or 0

                if cnt > 0:
                    # Delete matching player_stats
                    q_del = text(f"DELETE FROM player_stats WHERE player_id = :pid AND game_id IN ({','.join([':gid'+str(i) for i in range(len(game_ids))])})")
                    await conn.execute(q_del, params)
                    total_deleted_ps += cnt

                # After deleting player_stats, try deleting games that have no remaining player_stats
                for gid in game_ids:
                    q_del_game = text("DELETE FROM games WHERE id = :gid AND NOT EXISTS (SELECT 1 FROM player_stats WHERE game_id = :gid)")
                    await conn.execute(q_del_game, {"gid": gid})
                    # Check if game still exists
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

    pairs = collect_player_date_pairs(dirpath, args.pattern)
    if not pairs:
        print("No synthetic audit (player,date) pairs found.")
        return 0

    dbfile = Path("./dev.db")
    if args.backup and dbfile.exists():
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        bak = dbfile.with_name(f"dev.db.{ts}.bak")
        print(f"Backing up {dbfile} -> {bak}")
        shutil.copy(dbfile, bak)

    print(f"Deleting {len(pairs)} synthetic (player,date) pairs from DB...")
    asyncio.run(_delete_pairs(pairs))
    print("Done.")


if __name__ == "__main__":
    main()
