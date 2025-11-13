import sqlite3
import json

def main():
    conn = sqlite3.connect('dev.db')
    cur = conn.cursor()
    rows = list(cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table'"))
    out = []
    for name, sql in rows:
        out.append({"name": name, "sql": sql})
    print(json.dumps(out, indent=2))
    conn.close()

if __name__ == '__main__':
    main()
