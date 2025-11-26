from fastapi.testclient import TestClient

from backend.fastapi_nba import app


def test_health_embeddings_endpoint():
    client = TestClient(app)
    resp = client.get("/health/embeddings")
    assert resp.status_code == 200
    data = resp.json()
    assert "ok" in data
    # source is provided (live|fallback|None)
    assert "source" in data
    # latency may be present when ok
    assert isinstance(data.get("ok"), bool)
