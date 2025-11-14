"""Upsert audit JSON files into the dev DB (guarded).

Reads JSON files from an audit directory (default `backend/ingest_audit`) and
optionally upserts their normalized contents into the dev DB. By default the
script runs in dry-run mode and only prints summary counts. To commit you must
pass both `--commit` and `--confirm`.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import List

from backend.services.nba_normalize import canonicalize_rows


async def _upsert(player: str, rows: List[dict]):
    # import the upsert helper from populate script (dev-only helper)
    from backend.scripts.populate_dev_db_from_nba import upsert_into_db

    await upsert_into_db(player, rows)


def read_audit_file(path: Path) -> List[dict]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data


def normalize_for_upsert(raw_rows: List[dict]) -> List[dict]:
    # Use canonicalizer to normalize and dedupe, then map to keys expected
    # by upsert_into_db: include 'gameId'/'gameDate' and 'statValue'/'statType'.
    cans = canonicalize_rows(raw_rows)
    out = []
    for r in cans:
        # prefer canonical keys but keep original identifiers
        gid_raw = r.get("game_id") or r.get("GAME_ID") or r.get("gameId") or r.get("id")
        gdate = r.get("game_date") or r.get("GAME_DATE") or r.get("gameDate")
        pts = r.get("pts") or r.get("PTS") or r.get("stat_value")

        # Coerce or synthesize integer game id to match DB schema (games.id is Integer).
        # If the upstream id is numeric, keep it. Otherwise produce a stable surrogate.
        gid = None
        try:
            if gid_raw is None:
                gid = None
            else:
                gid = int(gid_raw)
        except Exception:
            # Stable surrogate: hash the raw id into a 32-bit positive integer
            gid = abs(hash(str(gid_raw))) % (10 ** 9)

        out.append({"gameId": gid, "gameDate": gdate, "statValue": pts, "statType": "points"})
    return out


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default="backend/ingest_audit")
    p.add_argument("--pattern", default="*.json")
    p.add_argument("--commit", action="store_true")
    p.add_argument("--confirm", action="store_true")
    args = p.parse_args(argv)

    d = Path(args.dir)
    if not d.exists():
        print(f"Audit directory does not exist: {d}")
        return 2

    files = list(d.glob(args.pattern))
    if not files:
        print(f"No audit files found in {d}")
        return 0

    summary = {}
    loop = asyncio.get_event_loop()
    for f in files:
        # Derive player name from filename when possible
        name = f.stem.replace("raw_fetch_", "").replace("synth_fetch_", "").replace("_", " ")
        raw = read_audit_file(f)
        rows = normalize_for_upsert(raw)
        summary[name] = len(rows)
        print(f"{f.name}: normalized rows={len(rows)} (player='{name}')")
        if args.commit:
            if not args.confirm:
                print(f"Skipping commit for {name} because --confirm not provided")
            else:
                print(f"Upserting {len(rows)} rows for {name} into DB...")
                loop.run_until_complete(_upsert(name, rows))

    print("Summary:")
    for n, c in summary.items():
        print(f"  {n}: {c} rows")


if __name__ == "__main__":
    main()
