from backend.services.chroma_vector_store import ChromaVectorStore

print("Initializing ChromaVectorStore...")
store = ChromaVectorStore(
    persist_directory="./chroma_data_test", collection_name="test_statmuse"
)
print("Initialized client and collection")

# Create a deterministic vector (length 384) and add
vec = [0.01] * int(__import__("os").environ.get("OLLAMA_EMBEDDING_DIM", "384"))
store.add("test1", vec, {"text": "hello test"})
print("Added vector id=test1")

res = store.search(vec, top_k=1)
print("Search result:", res)

# Confirm persistence file created (best-effort)
import os

print("Persist dir exists:", os.path.exists("./chroma_data_test"))
