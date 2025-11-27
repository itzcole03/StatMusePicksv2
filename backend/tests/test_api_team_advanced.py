import pytest
from fastapi.testclient import TestClient

from backend.fastapi_nba import app

client = TestClient(app)


def test_team_advanced_from_cached_logs():
    payload = {"team_id": 1610612744, "seasons": ["2023-24"]}
    resp = client.post("/api/team_advanced?use_fallback=true", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("team_id") == 1610612744
    adv = body.get("advanced")
    assert isinstance(adv, dict)
    per = adv.get("per_season")
    assert "2023-24" in per
    stats = per["2023-24"]

    # Derived from backend/data/cached_game_logs/team_1610612744_2023-24.json
    # PTS: [120,115] => avg 117.5
    # OPP_PTS: [110,118] => avg 114
    # PTS_diff = 3.5
    assert pytest.approx(stats.get("PTS_avg", 0), rel=1e-3) == 117.5
    assert pytest.approx(stats.get("OPP_PTS_avg", 0), rel=1e-3) == 114.0
    assert pytest.approx(stats.get("PTS_diff", 0), rel=1e-3) == pytest.approx(
        3.5, rel=1e-3
    )

    # FG% = sum(FGM)/sum(FGA) = (45+42)/(85+88) = 87/173 ~= 0.50289
    assert pytest.approx(stats.get("FG_pct", 0), rel=1e-3) == pytest.approx(
        87.0 / 173.0, rel=1e-3
    )

    # FT% = 29/38 ~= 0.763157
    assert pytest.approx(stats.get("FT_pct", 0), rel=1e-3) == pytest.approx(
        29.0 / 38.0, rel=1e-3
    )
