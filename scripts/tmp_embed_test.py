import os

os.environ["OLLAMA_EMBEDDINGS_FALLBACK"] = "true"
os.environ["OLLAMA_EMBEDDING_DIM"] = "64"
from backend.services.llm_feature_service import LLMFeatureService
from backend.services.vector_store import InMemoryVectorStore

s = InMemoryVectorStore()
svc = LLMFeatureService(default_model="embeddinggemma", vector_store=s)
items = [
    ("s1", "The quick brown fox jumps over the lazy dog.", {}),
    ("s2", "A slow yellow dog sleeps under the bright sun.", {}),
    ("s3", "Quantum physics and deep learning advances in 2025.", {}),
]
print("calling index_texts...")
indexed = svc.index_texts(items)
print("indexed:", indexed)
for id, text, meta in items:
    emb = svc.generate_embedding(text)
    print(id, "emb", type(emb), (len(emb) if emb else None), svc._last_embedding_source)
print("vector store contents:", s.all_items())
