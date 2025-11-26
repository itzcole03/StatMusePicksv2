import os
import json
from sqlalchemy import create_engine, select
from backend.models.model_metadata import ModelMetadata


class M:
    pass


def test_model_metadata_feature_list_db(tmp_path):
    # Use a temporary sqlite file for sync DB
    db_path = tmp_path / 'test_meta.db'
    url = f"sqlite:///{db_path}"
    os.environ['DATABASE_URL'] = url

    # Create table schema in the test DB
    engine = create_engine(url, future=True)
    ModelMetadata.__table__.create(engine)

    # Create a dummy model object with feature list
    m = M()
    m._feature_list = ['a', 'b', 'c']

    from backend.services.model_registry import ModelRegistry
    reg = ModelRegistry(model_dir=str(tmp_path / 'models'))
    reg.save_model('DB Player', m, version='v9', notes='db-test')

    # Query row and ensure feature_list column present and matches
    with engine.begin() as conn:
        sel = select(ModelMetadata.__table__).where(ModelMetadata.__table__.c.name == 'DB Player')
        row = conn.execute(sel).first()
    assert row is not None
    # depending on DB support, feature_list may be JSON string or native list
    val = row._mapping.get('feature_list')
    if val is None:
        # try parsing notes
        notes = row._mapping.get('notes')
        try:
            parsed = json.loads(notes)
            assert parsed.get('feature_list') == ['a', 'b', 'c']
        except Exception:
            assert False, 'feature_list not found in DB row'
    else:
        # if it's a string, attempt to load
        if isinstance(val, str):
            parsed = json.loads(val)
            assert parsed == ['a', 'b', 'c']
        else:
            assert list(val) == ['a', 'b', 'c']
