"""Periodic indexing script (simple): index sample news and persist mapping to JSON.

This script is intended as a simple runnable example. In production, wire this
into your ingestion pipeline and use a proper DB for persistence.

Run: python backend/scripts/index_news_periodic.py
"""
import json
import os
from datetime import datetime
from backend.services.llm_feature_service import create_default_service

OUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'artifacts', 'vector_index.json')

SAMPLES = [
    {"id": "news:2001", "text": "Player A listed as questionable with ankle sprain.", "meta": {"player": "A"}},
    {"id": "game:20251123", "text": "Team B beat Team C 98-95; star scored 28 points.", "meta": {"type": "game"}},
]


def load_existing(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"indexed_at": None, "items": []}


def save_index(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2)


def main():
    svc = create_default_service()
    items_to_index = []
    for s in SAMPLES:
        items_to_index.append((s['id'], s['text'], {**s.get('meta', {}), 'text': s['text']}))

    indexed = svc.index_texts(items_to_index)
    now = datetime.utcnow().isoformat() + 'Z'
    existing = load_existing(OUT_PATH)
    existing['indexed_at'] = now
    # append new items metadata
    for id in indexed:
        # find sample
        hits = [s for s in SAMPLES if s['id'] == id]
        if hits:
            existing['items'].append({'id': id, 'meta': hits[0]['meta'], 'indexed_at': now})

    save_index(OUT_PATH, existing)
    print('Indexed', indexed)


if __name__ == '__main__':
    main()
