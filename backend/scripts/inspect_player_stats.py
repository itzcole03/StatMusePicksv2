import os
import sqlite3

p = r"C:\Users\bcmad\Downloads\StatMusePicksv2\dev.db"
print("DB path:", p, "exists:", os.path.exists(p))
if not os.path.exists(p):
    raise SystemExit("dev.db not found")
conn = sqlite3.connect(p)
cur = conn.cursor()
try:
    cur.execute(
        "SELECT player_id, COUNT(*) FROM player_stats GROUP BY player_id ORDER BY COUNT(*) DESC LIMIT 10"
    )
    top10 = cur.fetchall()
    print("top10 player counts:", top10)

    cur.execute("PRAGMA table_info('player_stats')")
    print("player_stats schema:", cur.fetchall())

    cur.execute(
        "SELECT player_id FROM player_stats GROUP BY player_id ORDER BY COUNT(*) DESC LIMIT 1"
    )
    row = cur.fetchone()
    if row:
        top = row[0]
        cur.execute(
            "SELECT * FROM player_stats WHERE player_id=? ORDER BY game_date LIMIT 5",
            (top,),
        )
        sample = cur.fetchall()
        print("sample rows for", top, sample)
    else:
        print("no player rows found")
finally:
    conn.close()
