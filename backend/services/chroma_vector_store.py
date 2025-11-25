"""Optional ChromaDB-backed vector store adapter.

If `chromadb` is not installed this module raises on import; code paths
should fall back to `InMemoryVectorStore` when Chromadb is unavailable.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    import chromadb
    from chromadb.config import Settings
except Exception as e:
    chromadb = None  # type: ignore


class ChromaVectorStore:
    def __init__(self, persist_directory: Optional[str] = None, collection_name: str = "statmuse"):
        if chromadb is None:
            raise RuntimeError("chromadb is not installed; install with `pip install chromadb` to use ChromaVectorStore")
        # Attempt a few client initialization strategies to be compatible with
        # different chromadb versions / migrations.
        self.client = None
        try:
            # preferred: no-arg constructor (newer chromadb)
            self.client = chromadb.Client()
        except Exception:
            try:
                # fallback: Settings-based constructor (older chromadb)
                settings = Settings()
                if persist_directory:
                    settings = Settings(chroma_db_impl="duckdb+parquet", persist_directory=persist_directory)
                self.client = chromadb.Client(settings=settings)
            except Exception as e:
                # surface a helpful error
                raise RuntimeError(f"Failed to initialize chromadb client: {e}")
        # create or get collection
        self.collection = self.client.get_or_create_collection(name=collection_name)

    def add(self, id: str, embedding: List[float], metadata: Optional[Dict[str, Any]] = None) -> None:
        # chroma expects lists for ids/embeddings/metadata
        self.collection.add(ids=[id], embeddings=[embedding], metadatas=[metadata or {}], documents=[metadata.get('text') if metadata and 'text' in metadata else ''])

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        res = self.collection.query(query_embeddings=[query_embedding], n_results=top_k)
        # res contains keys: 'ids', 'distances', 'metadatas'
        ids = res.get('ids', [[]])[0]
        distances = res.get('distances', [[]])[0]
        metadatas = res.get('metadatas', [[]])[0]
        out = []
        for id, dist, meta in zip(ids, distances, metadatas):
            # chroma returns distances (lower is better) unless configured for cosine
            # leave as-is; caller can interpret
            out.append({"id": id, "score": float(1.0 - dist) if dist is not None else 0.0, "metadata": meta})
        return out

    def all_items(self) -> List[Dict[str, Any]]:
        # chroma doesn't provide direct list of all embeddings in API; use query with no filter
        # As a best-effort, return empty list — this method is primarily for in-memory store debugging.
        return []
