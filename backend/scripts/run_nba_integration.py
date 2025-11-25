"""Manual runner to exercise `nba_stats_client` against the real `nba_api`.

Usage:
  set NBA_INTEGRATION=1
  python backend/scripts/run_nba_integration.py

This script is intentionally minimal and intended for local developer use.
"""
import os
import json
import sys

from backend.services import nba_stats_client as nbc


def main():
    if nbc.players is None:
        print("nba_api is not installed. Install it to run this script.")
        sys.exit(2)

    if os.getenv("NBA_INTEGRATION", "") != "1":
        print("Set NBA_INTEGRATION=1 to allow real network integration tests.")
        sys.exit(2)

    name = "LeBron James"
    print(f"Resolving player id for: {name}")
    pid = nbc.find_player_id_by_name(name)
    print("Player id:", pid)
    if not pid:
        print("Could not resolve player id; aborting.")
        return

    print("Fetching recent games (limit=5)")
    recent = nbc.fetch_recent_games(pid, limit=5)
    print(json.dumps(recent, indent=2, default=str))


if __name__ == "__main__":
    main()
