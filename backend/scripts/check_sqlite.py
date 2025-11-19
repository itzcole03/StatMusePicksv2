import sqlite3
import os

DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'dev_migrations.db')
print('DB path:', DB)
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dataset_versions';")
print('tables:', c.fetchall())
conn.close()
