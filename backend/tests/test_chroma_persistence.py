import json
import os

import pytest


@pytest.mark.parametrize("dim", [8, 64])
def test_chroma_persistence_across_restarts(tmp_path, dim):
    """Verify that Chroma persists added vectors to disk and they can be
    retrieved after creating a new client pointing at the same persist dir.
    """
    # Skip if chromadb isn't installed in the environment
    pytest.importorskip('chromadb')

    from backend.services.chroma_vector_store import ChromaVectorStore

    persist_dir = str(tmp_path / "chroma_persist")
    # use a unique collection name per test to avoid cross-test collisions
    collection_name = f"pytest_persist_test_{tmp_path.name}"

    # ensure persist dir exists for chromadb
    os.makedirs(persist_dir, exist_ok=True)

    # Create first client and add a vector
    store1 = ChromaVectorStore(persist_directory=persist_dir, collection_name=collection_name)
    vec = [0.01 * i for i in range(dim)]
    store1.add("vec1", vec, {"text": "hello persist"})

    # Ensure we can find it immediately
    res1 = store1.search(vec, top_k=1)
    assert res1 and any(r.get('id') == 'vec1' for r in res1)

    # Attempt to flush/persist any in-memory state then delete the client
    try:
        persist_fn = getattr(store1.client, 'persist', None)
        if callable(persist_fn):
            persist_fn()
    except Exception:
        pass
    # Delete the client object to simulate a restart (best-effort)
    try:
        del store1
    except Exception:
        pass

    # Create a second client pointed at the same persist dir and collection
    store2 = ChromaVectorStore(persist_directory=persist_dir, collection_name=collection_name)
    res2 = store2.search(vec, top_k=5)

    # Assert the previously added vector is present after reinitialization
    assert any(r.get('id') == 'vec1' for r in res2), f"Expected vec1 in results, got: {json.dumps(res2)}"

    # Optional: inspect persist dir to ensure files exist (best-effort)
    assert os.path.exists(persist_dir)
