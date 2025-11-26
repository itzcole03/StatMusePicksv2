import os

from backend.services.llm_feature_service import LLMFeatureService

os.environ["OLLAMA_EMBEDDINGS_FALLBACK"] = "true"
os.environ["OLLAMA_EMBEDDING_DIM"] = "64"
svc = LLMFeatureService(default_model="embeddinggemma")
print("client repr:", svc.client)
print("client has embeddings?", hasattr(svc.client, "embeddings"))
print("client has _has_ollama?", getattr(svc.client, "_has_ollama", None))
print("client base url:", getattr(svc.client, "_base_url", None))
try:
    out = svc.client.embeddings(model="embeddinggemma", input="test")
    print("client.embeddings returned:", type(out), (len(out) if out else None))
except Exception as e:
    print("client.embeddings raised:", e)
