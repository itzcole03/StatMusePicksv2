import os
from fastapi.testclient import TestClient

import pytest

from backend.fastapi_nba import app


client = TestClient(app)


def test_player_advanced_with_fallback():
    payload = {"player": "Stephen Curry", "seasons": ["2023-24", "2022-23"]}
    resp = client.post("/api/player_advanced?use_fallback=true", json=payload)
    assert resp.status_code == 200
    j = resp.json()
    assert j.get("player") == "Stephen Curry"
    assert "advanced" in j
    adv = j["advanced"]
    assert isinstance(adv.get("per_season"), dict)


def test_player_advanced_without_fallback():
    payload = {"player": "Stephen Curry", "seasons": ["2023-24", "2022-23"]}
    resp = client.post("/api/player_advanced?use_fallback=false", json=payload)
    assert resp.status_code == 200
    j = resp.json()
    assert j.get("player") == "Stephen Curry"
    # Without fallback, advanced may be empty per-season depending on nba_api availability
    assert "advanced" in j
