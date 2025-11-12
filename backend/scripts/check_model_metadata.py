"""Query the `model_metadata` table and print recent rows.
Uses `DATABASE_URL` env var (converted to sync URL when needed).
"""
import os
from sqlalchemy import create_engine, text


def sync_db_url(raw):
    if not raw:
        return "sqlite:///./dev.db"
    if "${" in raw:
        return "sqlite:///./dev.db"
    sync = raw.replace("+aiosqlite", "").replace("+asyncpg", "").replace("+asyncmy", "")
    return sync


def main():
    raw = os.environ.get('DATABASE_URL')
    url = sync_db_url(raw)
    print('Using DB URL:', url)
    engine = create_engine(url, future=True)
    with engine.connect() as conn:
        res = conn.execute(text('select id, name, version, path, notes, created_at from model_metadata order by id desc limit 5'))
        rows = res.fetchall()
        if not rows:
            print('No rows found in model_metadata')
            return
        for r in rows:
            print(dict(r._mapping))

if __name__ == '__main__':
    main()
