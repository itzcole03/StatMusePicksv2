import os

from fastapi.testclient import TestClient

from backend.main import app


def test_batch_player_context_returns_results():
    # enable deterministic dev mock context so the endpoint returns sample recent games
    os.environ.setdefault("DEV_MOCK_CONTEXT", "1")

    client = TestClient(app)

    payload = [{"player": "LeBron James", "limit": 3}]

    resp = client.post("/api/batch_player_context", json=payload)
    assert resp.status_code == 200, resp.text

    data = resp.json()
    # Support both shapes: {'results': [...], 'errors': [...]} or a plain list of results
    if isinstance(data, dict):
        assert "results" in data and "errors" in data
        assert len(data["results"]) == 1
        res = data["results"][0]
        assert res.get("ok") is True
        ctx = res.get("context")
    else:
        # older fastapi_nba returns a list of summaries directly
        assert isinstance(data, list)
        assert len(data) == 1
        ctx = data[0]

    assert isinstance(ctx, dict)
    # recentGames or recent_games may be present depending on handler
    recent = ctx.get("recentGames") or ctx.get("recent_games") or ctx.get("recent")
    assert recent is None or isinstance(recent, (list, str))
