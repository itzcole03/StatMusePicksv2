def test_tool_call_flow(monkeypatch):
    """Simulate a model tool call for `web_search` and verify end-to-end flow.

    The fake client returns a tool_call dict on the first generate(), then a
    structured dict on the second generate(). We patch `web_search` to return
    a deterministic snippet so the flow is fully deterministic.
    """
    calls = {"generate": 0}

    class FakeClient:
        def generate(self, **kwargs):
            calls["generate"] += 1
            if calls["generate"] == 1:
                # instruct the service to call the web_search tool
                return {"tool_call": {"name": "web_search", "arguments": {"query": "PlayerX injury"}}}
            # second call: return a structured JSON-like dict matching the Pydantic schema
            return {
                "injury_status": "questionable",
                "morale_score": 65,
                "news_sentiment": -0.4,
                "trade_sentiment": 0.0,
                "motivation": 0.7,
            }

    # patch the client used inside llm_feature_service
    monkeypatch.setattr("backend.services.llm_feature_service.get_default_client", lambda: FakeClient())

    # patch web_search to a deterministic string and record calls
    web_calls = {}

    def fake_web_search(q: str) -> str:
        web_calls["q"] = q
        return "Recent report: Player suffered a minor sprain; listed as questionable."

    monkeypatch.setattr("backend.services.web_search.web_search", fake_web_search)

    # now call the service
    from backend.services.llm_feature_service import LLMFeatureService

    svc = LLMFeatureService()
    out = svc.extract_from_text("PlayerX", "")

    assert out["injury_status"] == "questionable"
    assert out["morale_score"] == 65
    assert abs(out["news_sentiment"] + 0.4) < 1e-6
    assert web_calls.get("q") == "PlayerX injury"
    assert calls["generate"] >= 2
