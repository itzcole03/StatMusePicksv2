"""Run the PER/WS prototype for a small list of players and persist results.

Usage:
  python backend/scripts/compute_per_ws_sample.py --players "Stephen Curry,Kevin Durant" --seasons 2024-25,2023-24
"""

from __future__ import annotations

import argparse
import datetime
import json
import os

from backend.services import nba_stats_client
from backend.services.per_ws_from_playbyplay import compute_player_season_estimates


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--players", default="", help="Comma-separated player full names")
    p.add_argument("--seasons", default="2024-25", help="Comma-separated seasons")
    return p.parse_args()


def main():
    args = parse_args()
    names = [n.strip() for n in args.players.split(",") if n.strip()]
    seasons = [s.strip() for s in args.seasons.split(",") if s.strip()]
    results = {}

    for name in names:
        pid = nba_stats_client.find_player_id_by_name(name)
        if not pid:
            results[name] = {"error": "player id not found"}
            continue
        est = compute_player_season_estimates(pid, seasons)
        results[name] = {"player_id": pid, "seasons": seasons, "estimates": est}

    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    repo_root = os.path.dirname(os.path.dirname(__file__))
    out_dir = os.path.join(repo_root, "models_store")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"per_ws_playbyplay_sample_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)

    print(f"Wrote results to: {out_path}")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
