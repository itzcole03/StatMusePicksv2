import json

from backend.models import VectorIndex
from backend.services.vector_indexer import VectorIndexer


def test_vector_indexer_run_once(tmp_path):
    # prepare temp sqlite file
    db_file = tmp_path / "test_vector_indexer.db"
    db_url = f"sqlite:///{db_file}"

    # prepare JSONL source
    src = tmp_path / "items.jsonl"
    items = [
        {"id": "news:1", "text": "Player A left ankle sprain"},
        {"id": "news:2", "text": "Player B cleared to play"},
    ]
    with open(src, "w", encoding="utf-8") as fh:
        for it in items:
            fh.write(json.dumps(it) + "\n")

    idx = VectorIndexer(db_url=db_url, source_file=str(src), interval_seconds=1)

    # replace real service with a fake that simply echoes back ids
    class FakeSvc:
        def __init__(self):
            self.default_model = "testmodel"

        def index_texts(self, items_list):
            # return the list of ids to indicate they were 'indexed'
            return [it[0] for it in items_list]

    idx.svc = FakeSvc()

    count = idx.run_once()
    assert count == 2

    # verify DB rows were created
    session = idx.Session()
    try:
        rows = session.query(VectorIndex).all()
        assert len(rows) == 2
        ids = {r.source_id for r in rows}
        assert ids == {"news:1", "news:2"}
    finally:
        session.close()
