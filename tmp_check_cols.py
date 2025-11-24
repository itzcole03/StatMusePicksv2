from sqlalchemy import create_engine, inspect

eng = create_engine('sqlite:///./dev.db')
ins = inspect(eng)
cols = ins.get_columns('model_metadata')
print([c['name'] for c in cols])
