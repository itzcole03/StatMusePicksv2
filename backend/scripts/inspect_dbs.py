import sqlite3, os
candidates = [
    os.path.join(os.path.dirname(os.path.dirname(__file__)), 'dev_migrations.db'),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), 'dev.db'),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'dev.db'),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'backend', 'dev.db')
]
# normalize and dedupe
candidates = [os.path.abspath(p) for p in candidates]
seen = set()
uniq = []
for p in candidates:
    if p not in seen:
        seen.add(p)
        uniq.append(p)

for p in uniq:
    print('DB:', p)
    if not os.path.exists(p):
        print('  MISSING')
        continue
    try:
        conn = sqlite3.connect(p)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print('  tables:', tables)
        if 'player_stats' in tables:
            try:
                cur.execute('SELECT COUNT(*) FROM player_stats')
                print('  player_stats rows:', cur.fetchone()[0])
            except Exception as e:
                print('  error counting player_stats:', e)
        conn.close()
    except Exception as e:
        print('  error opening DB:', e)
