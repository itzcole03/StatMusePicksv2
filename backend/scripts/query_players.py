"""Simple DB inspection helper to print players with Stephen/Curry and sample nba_player_id rows.

Run from the repo root: python backend/scripts/query_players.py
"""
import sqlite3


def main():
    conn = sqlite3.connect("dev.db")
    cur = conn.cursor()
    cur.execute('select id,nba_player_id,name from players where name like "%Stephen%" or name like "%Curry%"')
    print("Stephen/Curry rows:", cur.fetchall())
    cur.execute('select id,nba_player_id,name from players where nba_player_id is not null limit 20')
    print("Sample nba_player_id rows:", cur.fetchall())
    conn.close()


if __name__ == '__main__':
    main()
