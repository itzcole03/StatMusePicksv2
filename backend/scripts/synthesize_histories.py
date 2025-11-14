"""Synthesize deterministic player game histories for dev/testing.

Generates simple deterministic game logs for each player and writes JSON
audit files to `backend/ingest_audit/` by default. Files are compatible with
the canonicalizer and the ingestion pipeline.

Usage:
  python backend/scripts/synthesize_histories.py --players "Name1,Name2" --min-games 50

Options:
  --players    Comma-separated player full names
  --min-games  Minimum number of games to synthesize per player (int)
  --out-dir    Output directory for JSON audits (defaults to backend/ingest_audit)
  --dry-run    When set, only prints summary and does not write files
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, timedelta
from typing import List


def synth_for_player(name: str, min_games: int) -> List[dict]:
    """Create a deterministic list of game rows for `name` with at least
    `min_games` entries.
    """
    rows = []
    # Start date and simple per-day increments to produce unique dates
    start = date(2019, 10, 1)
    player_id = abs(hash(name)) % 10_000 + 1000
    for i in range(min_games):
        gdate = start + timedelta(days=i * 3)
        gid = f"SYN-{player_id}-{i:04d}"
        # Basic attributes matching what canonicalizer expects
        rows.append(
            {
                "GAME_ID": gid,
                "GAME_DATE": gdate.isoformat(),
                "PLAYER_ID": player_id,
                "SEASON_ID": f"{gdate.year}-{str(gdate.year+1)[-2:]}",
                "PTS": 10 + (i % 30),
                "REB": 2 + (i % 10),
                "AST": 1 + (i % 8),
            }
        )
    return rows


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--players", required=True)
    p.add_argument("--min-games", type=int, default=50)
    p.add_argument("--out-dir", default="backend/ingest_audit")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    players = [s.strip() for s in args.players.split(",") if s.strip()]
    os.makedirs(args.out_dir, exist_ok=True)
    summary = {}
    for name in players:
        rows = synth_for_player(name, args.min_games)
        fname = os.path.join(args.out_dir, f"synth_fetch_{name.replace(' ', '_')}.json")
        summary[name] = {"rows": len(rows), "path": fname}
        if not args.dry_run:
            with open(fname, "w", encoding="utf-8") as fh:
                json.dump(rows, fh, indent=2)

    # Print summary
    for n, info in summary.items():
        print(f"{n}: rows={info['rows']} path={info['path']}")


if __name__ == "__main__":
    main()
