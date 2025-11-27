import json
import os

print("ENV VARS:")
print("VECTOR_STORE=", os.environ.get("VECTOR_STORE"))
print("CHROMA_PERSIST_DIR=", os.environ.get("CHROMA_PERSIST_DIR"))
print("OLLAMA_DEFAULT_MODEL=", os.environ.get("OLLAMA_DEFAULT_MODEL"))

# Ensure repo import path
try:
    from backend.services.llm_feature_service import create_default_service
except Exception as e:
    print("import error:", e)
    raise

svc = create_default_service()
print("Service default_model:", svc.default_model)
print("Vector store type:", type(svc.vector_store).__name__)

# Index sample items
items = [
    (
        "chroma_id1",
        "Player scored 30 points and had a great game",
        {"text": "scored 30 points"},
    ),
    (
        "chroma_id2",
        "Injury report: player sprained ankle and is questionable",
        {"text": "sprained ankle"},
    ),
]
indexed = svc.index_texts(items)
print("Indexed ids:", indexed)

# Query similarity
q = "player has ankle injury"
res = svc.similarity_with_history(q, top_k=2)
print("Similarity result:", json.dumps(res, indent=2))

# Check persistence dir
p = os.environ.get("CHROMA_PERSIST_DIR") or "./chroma_data"
print("Checking persist dir:", p)
print("Exists:", os.path.exists(p))
print("Listing:", os.listdir(p) if os.path.exists(p) else [])
