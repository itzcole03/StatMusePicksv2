from backend.services.llm_feature_service import LLMFeatureService
from backend.services.vector_store import InMemoryVectorStore
import os
os.environ['OLLAMA_EMBEDDINGS_FALLBACK']='true'
os.environ['OLLAMA_EMBEDDING_DIM']='64'
svc=LLMFeatureService(default_model='embeddinggemma', vector_store=InMemoryVectorStore())
svc.client=None
print('client set to None')
emb=svc.generate_embedding('The quick brown fox jumps over the lazy dog.')
print('emb type:', type(emb), 'len', (len(emb) if emb else None), 'last_source', svc._last_embedding_source)
