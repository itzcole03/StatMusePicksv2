from sqlalchemy import create_engine, text
import os

sync = os.environ.get('DATABASE_URL') or 'sqlite:///./dev.db'
sync = sync.replace('+aiosqlite','').replace('+asyncpg','').replace('+asyncmy','')
engine = create_engine(sync)
with engine.connect() as conn:
    try:
        # correct table names: `player_stats`, `players`, `games`
        r = conn.execute(text('SELECT count(*) FROM player_stats'))
        print('player_stats count:', r.scalar())
    except Exception as e:
        print('Error querying player_stats count:', e)
    try:
        q = '''
        SELECT p.name, ps.stat_type, ps.value, g.game_date
        FROM player_stats ps
        JOIN players p ON ps.player_id = p.id
        JOIN games g ON ps.game_id = g.id
        ORDER BY g.game_date DESC
        LIMIT 5
        '''
        r = conn.execute(text(q))
        print('\nLatest 5 player_stats rows:')
        for row in r:
            print(row)
    except Exception as e:
        print('Error querying sample rows:', e)
