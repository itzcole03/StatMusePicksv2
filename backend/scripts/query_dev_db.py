import os
import sqlite3

p = r"c:\Users\bcmad\Downloads\StatMusePicksv2\dev.db"
print("DB path:", p)
if not os.path.exists(p):
    print("DB_MISSING")
else:
    conn = sqlite3.connect(p)
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM player_stats")
        total = cur.fetchone()[0]
        print("total_player_stats_rows:", total)
    except Exception as e:
        print("count_error", e)
    try:
        cur.execute(
            "SELECT player_id, COUNT(*) FROM player_stats GROUP BY player_id ORDER BY COUNT(*) DESC LIMIT 5"
        )
        print("top_players:", cur.fetchall())
    except Exception as e:
        print("top_players_error", e)
    try:
        cur.execute(
            "SELECT player_id FROM player_stats GROUP BY player_id ORDER BY COUNT(*) DESC LIMIT 1"
        )
        top = cur.fetchone()
        if top:
            pid = top[0]
            cur.execute(
                "SELECT game_date, stat_value, line FROM player_stats WHERE player_id=? ORDER BY game_date LIMIT 5",
                (pid,),
            )
            print("sample_rows_for", pid, cur.fetchall())
    except Exception as e:
        print("sample_error", e)
    conn.close()
