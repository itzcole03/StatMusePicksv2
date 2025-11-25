import os
from backend.services.llm_feature_service import LLMFeatureService
from backend.services.vector_store import InMemoryVectorStore


def test_index_and_similarity():
    # Ensure deterministic fallback is enabled for test
    os.environ['OLLAMA_EMBEDDINGS_FALLBACK'] = 'true'
    os.environ['OLLAMA_EMBEDDING_DIM'] = '64'

    store = InMemoryVectorStore()
    svc = LLMFeatureService(default_model='embeddinggemma', vector_store=store)

    samples = [
        ("s1", "The quick brown fox jumps over the lazy dog.", {"type": "sample"}),
        ("s2", "A slow yellow dog sleeps under the bright sun.", {"type": "sample"}),
        ("s3", "Quantum physics and deep learning advances in 2025.", {"type": "sample"}),
    ]

    indexed = svc.index_texts(samples)
    assert set(indexed) == {"s1", "s2", "s3"}

    # Query similar to s1
    query = "A fox leaps over a sleeping dog"
    res = svc.similarity_with_history(query, top_k=3)

    assert 'top_matches' in res
    assert len(res['top_matches']) == 3
    assert isinstance(res['max_similarity'], float)
    assert isinstance(res['avg_topk_similarity'], float)

    # Ensure store has items
    all_items = store.all_items()
    assert len(all_items) == 3

    # Scores should be within -1..1
    for m in res['top_matches']:
        assert -1.0 <= m['score'] <= 1.0
