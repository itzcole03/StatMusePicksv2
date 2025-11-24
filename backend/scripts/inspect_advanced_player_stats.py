"""Inspect season-aggregated advanced player stats via nba_stats_client helpers.

Usage:
  python backend/scripts/inspect_advanced_player_stats.py --players "Stephen Curry,Kevin Durant" --seasons 2024-25,2023-24

Prints JSON output per player to stdout and writes a timestamped JSON file to
`backend/models_store/inspect_advanced_player_stats_<ts>.json`.
"""
from __future__ import annotations

import argparse
import json
import os
import datetime
from typing import List

from backend.services import nba_stats_client


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--players", default="", help="Comma-separated player full names")
    p.add_argument("--seasons", default="2024-25", help="Comma-separated seasons e.g. 2024-25,2023-24")
    return p.parse_args()


def main():
    args = parse_args()
    names = [n.strip() for n in args.players.split(",") if n.strip()]
    seasons = [s.strip() for s in args.seasons.split(",") if s.strip()]
    out = {}

    for name in names:
        pid = None
        try:
            pid = nba_stats_client.find_player_id_by_name(name)
        except Exception as e:
            pid = None
        if not pid:
            out[name] = {"error": "player id not found"}
            continue

        try:
            stats = nba_stats_client.get_advanced_player_stats_multi(pid, seasons, use_fallback=True)
            out[name] = {"player_id": pid, "seasons": seasons, "stats": stats}
        except Exception as e:
            out[name] = {"player_id": pid, "error": str(e)}

    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    repo_root = os.path.dirname(os.path.dirname(__file__))
    store_dir = os.path.join(repo_root, 'models_store')
    try:
        os.makedirs(store_dir, exist_ok=True)
    except Exception:
        pass

    out_path = os.path.join(store_dir, f"inspect_advanced_player_stats_{ts}.json")
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=2)

    print(json.dumps(out, indent=2))
    print(f"Wrote results to: {out_path}")


if __name__ == '__main__':
    main()
