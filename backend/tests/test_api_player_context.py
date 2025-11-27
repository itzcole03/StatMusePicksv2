import importlib

from fastapi.testclient import TestClient

app_mod = importlib.import_module("backend.fastapi_nba")
app = app_mod.app


def test_player_context_summary(monkeypatch):
    """Test that POST /api/player_context returns a summary when no season/game_date provided."""
    # Monkeypatch player_summary to return a deterministic dict
    monkeypatch.setattr(
        app_mod,
        "player_summary",
        lambda player, stat, limit, debug=0: {
            "player": player,
            "stat": stat,
            "recentGames": [],
            "seasonAvg": None,
            "fetchedAt": "now",
        },
    )

    client = TestClient(app)
    resp = client.post(
        "/api/player_context",
        json={"player": "LeBron James", "stat": "points", "limit": 5},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["player"] == "LeBron James"
    assert "fetchedAt" in data


def test_player_context_training_context(monkeypatch):
    """When season and game_date are provided, the richer training context should be returned."""
    svc = importlib.import_module("backend.services.nba_service")

    # Provide a deterministic training context
    sample_ctx = {
        "player": "Player X",
        "playerId": 7,
        "season": "2023-24",
        "recentGamesRaw": [],
        "seasonStats": {},
        "advancedStats": {},
        "fetchedAt": "now",
    }
    monkeypatch.setattr(
        svc,
        "get_player_context_for_training",
        lambda player, stat, game_date, season: sample_ctx,
    )

    client = TestClient(app)
    resp = client.post(
        "/api/player_context",
        json={"player": "Player X", "season": "2023-24", "game_date": "2024-01-01"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["player"] == "Player X"
    assert "playerId" in data and data["season"] == "2023-24"
