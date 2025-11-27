from fastapi.testclient import TestClient

from backend.fastapi_nba import app


def test_nba_status_endpoint():
    client = TestClient(app)
    resp = client.get("/api/nba_status")
    assert resp.status_code == 200
    data = resp.json()
    # required keys
    assert "nba_api_installed" in data
    assert "can_fetch_players" in data
    assert "cached_logs_exist" in data
    # sample_player may be None or dict
    assert "sample_player" in data
    # values should be booleans or None/dict as appropriate
    assert isinstance(data["nba_api_installed"], bool)
    assert isinstance(data["can_fetch_players"], bool)
    assert isinstance(data["cached_logs_exist"], bool)
    if data.get("sample_player") is not None:
        assert isinstance(data["sample_player"], dict)
