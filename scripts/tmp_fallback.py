import hashlib
import os
import random

os.environ["OLLAMA_EMBEDDINGS_FALLBACK"] = "true"
os.environ["OLLAMA_EMBEDDING_DIM"] = "64"
text = "The quick brown fox jumps over the lazy dog."
dim = int(os.environ.get("OLLAMA_EMBEDDING_DIM", "384"))
h = hashlib.sha256(text.encode("utf-8")).hexdigest()
seed = int(h[:16], 16)
rnd = random.Random(seed)
vec = [rnd.uniform(-1.0, 1.0) for _ in range(dim)]
print("len vec", len(vec))
print(vec[:5])
