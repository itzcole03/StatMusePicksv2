import json
import logging
import os
import sys
from glob import glob

# Ensure repo root is on sys.path so `backend` package imports work when running scripts
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from backend.services.data_ingestion_service import update_player_stats


def find_latest_audit(audit_dir):
    pattern = os.path.join(audit_dir, "games_raw_*.json")
    files = glob(pattern)
    if not files:
        return None
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def main():
    logging.basicConfig(
        level=logging.DEBUG, format="%(levelname)s:%(name)s:%(message)s"
    )
    audit_dir = os.path.join(repo_root, "backend", "ingest_audit")
    latest = find_latest_audit(audit_dir)
    if not latest:
        print("No audit file found in", audit_dir)
        return
    print("Using audit file:", latest)
    with open(latest, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    print("Calling update_player_stats with", len(data), "records")
    inserted = update_player_stats(data)
    print("update_player_stats returned inserted=", inserted)


if __name__ == "__main__":
    main()
