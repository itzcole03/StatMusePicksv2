"""Simple in-memory vector store for development and testing.

Provides add(id, embedding, metadata) and search(query_embedding, top_k).
Uses cosine similarity.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple


class InMemoryVectorStore:
    def __init__(self):
        # store as id -> (embedding, metadata)
        self._items: Dict[str, Tuple[List[float], Dict[str, Any]]] = {}

    def add(self, id: str, embedding: List[float], metadata: Optional[Dict[str, Any]] = None) -> None:
        self._items[id] = (embedding, metadata or {})

    def _cosine(self, a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = 0.0
        na = 0.0
        nb = 0.0
        for x, y in zip(a, b):
            dot += x * y
            na += x * x
            nb += y * y
        if na == 0 or nb == 0:
            return 0.0
        return dot / (math.sqrt(na) * math.sqrt(nb))

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        scores = []
        for id, (emb, meta) in self._items.items():
            score = self._cosine(query_embedding, emb)
            scores.append((score, id, meta))
        scores.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, id, meta in scores[:top_k]:
            results.append({"id": id, "score": float(score), "metadata": meta})
        return results

    def all_items(self) -> List[Dict[str, Any]]:
        return [{"id": id, "embedding": emb, "metadata": meta} for id, (emb, meta) in self._items.items()]
