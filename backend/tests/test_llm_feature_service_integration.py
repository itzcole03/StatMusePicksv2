from backend.services.llm_feature_service import LLMFeatureService, QualitativeFeatures


class DummyClient:
    def __init__(self, return_value):
        self._return = return_value

    def generate(self, **kwargs):
        # mimic the client returning a dict when response_format='json'
        return self._return


def test_extract_from_text_valid_json(monkeypatch):
    payload = {
        "injury_status": "questionable",
        "morale_score": 72,
        "news_sentiment": 0.2,
        "trade_sentiment": -0.1,
        "motivation": 0.8,
    }

    dummy = DummyClient(return_value=payload)

    # patch the default client used by the service (patch the symbol imported
    # into the llm_feature_service module)
    import backend.services.llm_feature_service as lfs

    monkeypatch.setattr(lfs, "get_default_client", lambda: dummy)

    svc = LLMFeatureService()
    out = svc.extract_from_text("Test Player", "Some context about the player")

    # Should validate against the Pydantic model and include keys
    assert isinstance(out, dict)
    vf = QualitativeFeatures.parse_obj(out)
    assert vf.injury_status == "questionable"
    assert vf.morale_score == 72


def test_extract_from_text_invalid_json_then_coerce(monkeypatch):
    # return shape missing keys / with different names
    raw = {
        "injury": "healthy",
        "morale": "60",
        "sentiment": "0.0",
        "tradeSentiment": 0.0,
        "motivation_score": 0.5,
    }

    dummy = DummyClient(return_value=raw)
    import backend.services.llm_feature_service as lfs

    monkeypatch.setattr(lfs, "get_default_client", lambda: dummy)

    svc = LLMFeatureService()
    out = svc.extract_from_text("Test Player", "Some context")

    # Coercion path should normalize types/keys into the schema
    assert isinstance(out, dict)
    vf = QualitativeFeatures.parse_obj(out)
    assert vf.injury_status in ("healthy", "questionable", "out")
    assert isinstance(vf.morale_score, int)
