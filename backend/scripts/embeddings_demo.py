"""Demo: index sample texts and query similarity using LLMFeatureService.

Run: python backend/scripts/embeddings_demo.py
"""

from backend.services.llm_feature_service import create_default_service


def main():
    svc = create_default_service()

    samples = [
        (
            "game:20250101",
            "Team A beat Team B 110-100. Star player recorded 30 points and left ankle appeared sore.",
            {"type": "game", "desc": "game summary"},
        ),
        (
            "news:1001",
            "Star player X listed as questionable with an ankle sprain; trade rumors minimal.",
            {"type": "news", "player": "X"},
        ),
        (
            "news:1002",
            "Coach fired after poor season; team morale low going into next game.",
            {"type": "news", "topic": "coach"},
        ),
    ]

    indexed = svc.index_texts(samples)
    print("Indexed IDs:", indexed)

    # show all items in store (if any)
    try:
        items = svc.vector_store.all_items()
        print(f"Vector store contains {len(items)} items")
        for it in items:
            print("-", it["id"], "meta:", it["metadata"])
            # report embedding source if available
            try:
                src = svc._last_embedding_source
                print(f"  embedding_source: {src}")
            except Exception:
                pass
    except Exception as e:
        print("Failed to read vector store items:", e)

    # similarity query
    query = "Player X has an ankle sprain and might be questionable for tonight."
    sim = svc.similarity_with_history(query, top_k=3)
    print("\nQuery:", query)
    print("Similarity result:", sim)


if __name__ == "__main__":
    main()
