def test_llm_feature_extraction_basic():
    from backend.services.llm_feature_service import LLMFeatureService

    svc = LLMFeatureService(redis_client=None)

    def tf(name: str) -> str:
        return f"{name} had an ankle sprain in practice but is expected to play; team morale high."

    res1 = svc.fetch_news_and_extract("LeBron James", "news_v1", tf)
    assert isinstance(res1, dict)
    assert "injury_sentiment" in res1
    assert "morale_score" in res1
    assert "motivation" in res1
    # repeated fetch should return cached (deterministic) result
    res2 = svc.fetch_news_and_extract("LeBron James", "news_v1", tf)
    assert res1 == res2


def test_llm_feature_range():
    from backend.services.llm_feature_service import LLMFeatureService

    svc = LLMFeatureService(redis_client=None)

    def tf(name: str) -> str:
        return "positive outlook and award buzz"

    r = svc.fetch_news_and_extract("Player X", "news_v1", tf)
    assert -1.0 <= r.get("injury_sentiment", 0.0) <= 1.0
    assert -1.0 <= r.get("morale_score", 0.0) <= 1.0
    assert 0.0 <= r.get("motivation", 0.0) <= 1.0
