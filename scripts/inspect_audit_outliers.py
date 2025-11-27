import json
import os
from glob import glob

AUDIT_DIR = os.path.join(os.path.dirname(__file__), "..", "backend", "ingest_audit")


def find_latest_audit():
    pattern = os.path.join(AUDIT_DIR, "games_raw_*.json")
    files = glob(pattern)
    if not files:
        return None
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def load_audit(path):
    recs = []
    with open(path, "r", encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                recs.append(json.loads(ln))
            except Exception:
                continue
    return recs


def main():
    path = find_latest_audit()
    if not path:
        print("No audit file found")
        return
    recs = load_audit(path)
    print(f"Loaded {len(recs)} records from {path}")

    try:
        # Import the outlier detection from the ingestion service
        from backend.services.data_ingestion_service import detect_outlier_values
    except Exception as e:
        print("Failed to import detect_outlier_values:", e)
        return

    outlier_idxs = detect_outlier_values(recs, field="value", z_thresh=3.0)
    print(f"Found {len(outlier_idxs)} outlier indices")
    for i in outlier_idxs:
        r = recs[i]
        print(
            f'Index {i}: player_name={r.get("player_name") or r.get("player")}, player_nba_id={r.get("player_nba_id")}, stat_type={r.get("stat_type")}, value={r.get("value")}, game_date={r.get("game_date")}'
        )


if __name__ == "__main__":
    main()
