import asyncio
import os
import pytest

from backend import fastapi_nba as appmod
from fastapi.testclient import TestClient


def test_batch_predict_timeout(monkeypatch):
    # force a very small per-item timeout
    monkeypatch.setenv("BATCH_PREDICT_ITEM_TIMEOUT", "0.01")

    async def slow_predict(*args, **kwargs):
        # sleep slightly longer than the timeout
        await asyncio.sleep(0.05)
        return {
            "player": kwargs.get('player_name') or (args[0] if args else "unknown"),
            "stat": kwargs.get('stat_type', 'points'),
            "line": kwargs.get('line', 0.0),
            "predicted_value": 12.3,
        }

    # monkeypatch the ml_service used by the app (predict must be awaitable)
    monkeypatch.setattr(appmod, "ml_service", type("M", (), {"predict": slow_predict})())

    with TestClient(appmod.app) as client:
        resp = client.post(
            "/api/batch_predict",
            json=[{"player": "LeBron James", "stat": "points", "line": 25.5}],
            timeout=10.0,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "predictions" in data
        preds = data["predictions"]
        assert len(preds) == 1
        assert preds[0].get("error") == "prediction timeout"
