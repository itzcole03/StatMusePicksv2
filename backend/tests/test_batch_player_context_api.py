from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_batch_player_context_basic():
    payload = [
        {"player": "LeBron James", "limit": 3},
        {"player": "", "limit": 2},
    ]

    resp = client.post("/api/batch_player_context", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    # The current implementation returns a list with one entry per request.
    assert isinstance(body, list)
    assert len(body) == 2

    # The second entry corresponds to the empty player and should contain an error
    assert any(("error" in (entry or {})) for entry in body)
