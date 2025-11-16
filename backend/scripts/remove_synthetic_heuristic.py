"""Heuristic-based removal of synthetic rows.

This script infers players from `synth_fetch_*.json` filenames, finds internal
player ids, then selects candidate `game_id` values for those players where:
- `game_id` is small (below `--max-game-id`, default 1_000_000), and
- `game_date` is within a recent window (default since `--since`),
These heuristics match how synthetic rows were inserted (autoincrement ids).

Run with `--backup --apply` to actually delete; by default it only reports candidates.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Tuple

from sqlalchemy import text

from backend import db


def collect_files(dirpath: Path, pattern: str) -> List[Path]:
    return [p for p in dirpath.glob(pattern) if p.is_file()]


def filename_to_name(p: Path) -> str:
    stem = p.stem
    if stem.startswith("synth_fetch_"):
        name = stem[len("synth_fetch_"):]
        return name.replace("_", " ")
    return stem.replace("_", " ")


async def find_candidates(files: List[Path], since: str, max_game_id: int) -> Dict[int, Set[int]]:
    """Return mapping internal_player_id -> set(game_id candidates)."""
    db._ensure_engine_and_session()
    since_dt = since
    out: Dict[int, Set[int]] = {}
    async with db.engine.begin() as conn:
        for p in files:
            name = filename_to_name(p)
            # find players by name (case-insensitive)
            q_players = text("SELECT id FROM players WHERE LOWER(name) = LOWER(:nm)")
            res = await conn.execute(q_players, {"nm": name})
            rows = res.mappings().all()
            if not rows:
                print(f"No player rows matching '{name}'")
                continue
            ids = [r["id"] for r in rows]
            for pid in ids:
                # select distinct small game_ids for this player with recent dates
                q = text(
                    "SELECT DISTINCT ps.game_id FROM player_stats ps JOIN games g ON g.id = ps.game_id "
                    "WHERE ps.player_id = :pid AND ps.game_id IS NOT NULL AND ps.game_id < :maxid AND g.game_date >= :since"
                )
                res2 = await conn.execute(q, {"pid": pid, "maxid": max_game_id, "since": since_dt})
                gids = {row[0] for row in res2.fetchall()}
                if gids:
                    out.setdefault(pid, set()).update(gids)
    return out


async def delete_candidates(candidates: Dict[int, Set[int]]) -> Tuple[int, int]:
    db._ensure_engine_and_session()
    total_ps = 0
    total_games = 0
    async with db.engine.begin() as conn:
        for pid, gids in candidates.items():
            gids_list = sorted(gids)
            # delete player_stats
            q_del_ps = text(f"DELETE FROM player_stats WHERE player_id = :pid AND game_id IN ({','.join([':gid'+str(i) for i in range(len(gids_list))])})")
            params = {"pid": pid}
            params.update({f"gid{i}": v for i, v in enumerate(gids_list)})
            # Count first
            q_count = text(f"SELECT COUNT(*) FROM player_stats WHERE player_id = :pid AND game_id IN ({','.join([':gid'+str(i) for i in range(len(gids_list))])})")
            cres = await conn.execute(q_count, params)
            cnt = cres.scalar() or 0
            if cnt > 0:
                await conn.execute(q_del_ps, params)
                total_ps += cnt

            # delete orphaned games
            for gid in gids_list:
                q_del_game = text("DELETE FROM games WHERE id = :gid AND NOT EXISTS (SELECT 1 FROM player_stats WHERE game_id = :gid)")
                await conn.execute(q_del_game, {"gid": gid})
                q_check = text("SELECT COUNT(*) FROM games WHERE id = :gid")
                rc = await conn.execute(q_check, {"gid": gid})
                still = rc.scalar() or 0
                if still == 0:
                    total_games += 1
    return total_ps, total_games


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default="backend/ingest_audit")
    p.add_argument("--pattern", default="synth_fetch_*.json")
    p.add_argument("--since", default="2025-01-01", help="Earliest game_date to consider (YYYY-MM-DD)")
    p.add_argument("--max-game-id", type=int, default=1_000_000, help="Upper bound for game_id considered synthetic")
    p.add_argument("--apply", action="store_true", help="Actually delete candidates")
    p.add_argument("--backup", action="store_true", help="Backup dev.db before deleting")
    args = p.parse_args(argv)

    dirpath = Path(args.dir)
    files = collect_files(dirpath, args.pattern)
    if not files:
        print("No synth audit files found; nothing to do.")
        return 0

    if args.backup:
        dbfile = Path("./dev.db")
        if dbfile.exists():
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            bak = dbfile.with_name(f"dev.db.{ts}.bak")
            print(f"Backing up {dbfile} -> {bak}")
            shutil.copy(dbfile, bak)

    print("Finding candidate game_ids for synth files...")
    candidates = asyncio.run(find_candidates(files, args.since, args.max_game_id))
    if not candidates:
        print("No candidate game_ids found for deletion.")
        return 0

    print("Candidate deletion summary:")
    total_gids = sum(len(s) for s in candidates.values())
    for pid, gids in candidates.items():
        print(f"  player_id={pid}: {len(gids)} candidate game_ids (sample: {sorted(list(gids))[:10]})")
    print(f"Total candidate player_stats to delete (approx): {total_gids}")

    if not args.apply:
        print("Dry-run mode: no rows deleted. Re-run with --apply --backup to delete.")
        return 0

    print("Applying deletions...")
    ps, gs = asyncio.run(delete_candidates(candidates))
    print(f"Deleted {ps} player_stats rows and {gs} orphaned games rows.")
    return 0


if __name__ == '__main__':
    main()
