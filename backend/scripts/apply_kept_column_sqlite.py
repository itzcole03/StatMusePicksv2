from sqlalchemy import create_engine, text
eng = create_engine('sqlite:///./dev.db')
with eng.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE model_metadata ADD COLUMN kept_contextual_features TEXT;"))
        print('column added')
    except Exception as e:
        print('error:', e)
