import importlib

from fastapi import HTTPException
from fastapi.testclient import TestClient

app_mod = importlib.import_module("backend.fastapi_nba")
app = app_mod.app


def _good_summary(player, stat, limit):
    return {
        "player": player,
        "stat": stat,
        "recentGames": [],
        "seasonAvg": None,
        "fetchedAt": "now",
    }


def _bad_summary(player, stat, limit):
    raise HTTPException(status_code=404, detail="player not found")


def test_batch_partial_failures(monkeypatch):
    # Good player returns data, bad player raises 404, empty player triggers client error
    monkeypatch.setattr(
        app_mod,
        "player_summary",
        lambda player, stat, limit, debug=0: (
            _good_summary(player, stat, limit)
            if player == "Good Player"
            else _bad_summary(player, stat, limit)
        ),
    )

    client = TestClient(app)
    payload = [
        {"player": "Good Player", "stat": "points", "limit": 5},
        {"player": "Bad Player", "stat": "points", "limit": 5},
        {"player": "", "stat": "points", "limit": 5},
    ]

    resp = client.post("/api/batch_player_context", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list) and len(data) == 3

    # First item should be a valid summary
    assert data[0].get("player") == "Good Player"
    assert "recentGames" in data[0]

    # Second item should be an error object
    assert data[1].get("player") == "Bad Player"
    assert "error" in data[1]

    # Third item (missing player) should report error 'player name required'
    assert data[2].get("error") is not None
