import json
import os
import sqlite3
from glob import glob

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "dev.db")
AUDIT_DIR = os.path.join(os.path.dirname(__file__), "..", "backend", "ingest_audit")


def print_counts(conn):
    cur = conn.cursor()
    for t in ("players", "games", "player_stats"):
        try:
            r = cur.execute(f"select count(*) from {t}").fetchone()[0]
        except Exception as e:
            r = f"ERROR: {e}"
        print(f"{t}: {r}")


def sample_table(conn, table, limit=5):
    cur = conn.cursor()
    try:
        rows = cur.execute(f"select * from {table} limit {limit}").fetchall()
    except Exception as e:
        print(f"{table} sample error: {e}")
        return
    print(f"\nSample rows from {table} (up to {limit}):")
    for r in rows:
        print(r)


def find_latest_audit():
    pattern = os.path.join(AUDIT_DIR, "games_raw_*.json")
    files = glob(pattern)
    if not files:
        return None
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def print_audit_sample(path, limit=10):
    print(f"\nReading audit file: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        data = None
        try:
            # Try JSON array first
            data = json.loads(text)
        except Exception:
            # Fallback: treat as JSONL (one JSON object per line)
            data = []
            for ln in text.splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    data.append(json.loads(ln))
                except Exception:
                    # ignore malformed lines but continue
                    continue
    except Exception as e:
        print(f"Failed to read audit file: {e}")
        return
    print(f"Total records in audit: {len(data)}")
    print(
        f"Printing first {min(limit, len(data))} records (showing keys and presence of player fields):"
    )
    for i, rec in enumerate(data[:limit], start=1):
        keys = list(rec.keys())
        has_player_name = (
            "player_name" in rec or "PLAYER_NAME" in rec or "player" in rec
        )
        has_player_id = (
            "player_nba_id" in rec or "Player_ID" in rec or "player_id" in rec
        )
        print(
            f"#{i}: keys={keys[:10]}{'...' if len(keys)>10 else ''} | has_player_name={has_player_name} | has_player_id={has_player_id}"
        )


def main():
    db_abspath = os.path.abspath(DB_PATH)
    print(f"dev.db path: {db_abspath}")
    if not os.path.exists(db_abspath):
        print("dev.db not found at expected location.")
    else:
        conn = sqlite3.connect(db_abspath)
        print_counts(conn)
        sample_table(conn, "players", 5)
        sample_table(conn, "games", 5)
        sample_table(conn, "player_stats", 5)
        conn.close()

    latest = find_latest_audit()
    if latest:
        print_audit_sample(latest, 10)
    else:
        print("No audit files found in", AUDIT_DIR)


if __name__ == "__main__":
    main()
