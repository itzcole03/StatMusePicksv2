"""Inspect model_metadata rows in the local `dev.db` SQLite database.

Usage: python scripts/inspect_model_metadata.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "dev.db"

if not DB.exists():
    print(f"dev.db not found at {DB}")
    raise SystemExit(1)

conn = sqlite3.connect(str(DB))
cur = conn.cursor()
try:
    cur.execute(
        "SELECT id,name,version,path,notes,created_at FROM model_metadata ORDER BY created_at DESC LIMIT 20"
    )
    rows = cur.fetchall()
    if not rows:
        print("No rows found in model_metadata")
    else:
        for r in rows:
            print(r)
except Exception as e:
    print("Query failed:", e)
finally:
    conn.close()
