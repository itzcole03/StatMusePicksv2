from fastapi.testclient import TestClient


def test_api_ollama_features_endpoint(monkeypatch):
    # Patch the llm_feature_service factory to return a fake service
    class FakeSvc:
        def extract_from_text(self, player_name, text, model=None):
            return {
                "injury_sentiment": -0.2,
                "morale_score": 0.1,
                "motivation": 0.5,
                "coaching_change_impact": 0.0,
            }

    monkeypatch.setattr(
        "backend.services.llm_feature_service.create_default_service", lambda: FakeSvc()
    )

    from backend.fastapi_nba import app

    client = TestClient(app)
    resp = client.post(
        "/api/ollama_features", json={"player": "Test Player", "text": "Test context"}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, dict)
    assert "morale_score" in data


def test_ollama_client_list_models_http_fallback(monkeypatch):
    # Simulate requests.get returning a JSON list of models
    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return ["m1", "m2"]

    def fake_get(url, headers=None, timeout=None):
        return FakeResp()

    monkeypatch.setattr("requests.get", fake_get)

    from backend.services.ollama_client import get_default_client

    client = get_default_client()
    models = client.list_models()
    # Accept either list or other json-like shapes but ensure models present
    assert models is not None
    # If it's a list it should contain our fake values
    if isinstance(models, list):
        assert "m1" in models


def test_inmemory_vector_store_search():
    from backend.services.vector_store import InMemoryVectorStore

    vs = InMemoryVectorStore()
    vs.add("a", [1.0, 0.0, 0.0], {"title": "one"})
    vs.add("b", [0.0, 1.0, 0.0], {"title": "two"})

    # Query should match 'a'
    res = vs.search([1.0, 0.0, 0.0], top_k=1)
    assert isinstance(res, list)
    assert len(res) == 1
    assert res[0]["id"] == "a"
