"""Cache all players to `backend/data/all_players.json` for offline lookups.

Useful when `nba_api` or network access is flaky. Run in the backend venv where
`nba_api` is installed to build the local cache.
"""

import json
import os

from backend.services.nba_stats_client import fetch_all_players


def main():
    lst = fetch_all_players()
    if not lst:
        print(
            "No players fetched; ensure `nba_api` is installed and network is available."
        )
        return
    repo_root = os.path.dirname(os.path.dirname(__file__))
    out_dir = os.path.join(repo_root, "backend", "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "all_players.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(lst, fh)
    print(f"Wrote {len(lst)} players to {out_path}")


if __name__ == "__main__":
    main()
