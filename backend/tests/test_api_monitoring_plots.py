from fastapi.testclient import TestClient
import os
from backend.main import app


def test_list_and_get_plots():
    # Ensure sample plots exist in tests/data (created by earlier smoke runs)
    client = TestClient(app)
    res = client.get("/api/monitoring/fallback_plots")
    assert res.status_code == 200
    data = res.json()
    assert data.get("ok") is True
    plots = data.get("plots")
    assert isinstance(plots, list)

    # If any plots found, request the first one
    if plots:
        first = plots[0]
        # Test fetching by absolute path
        res2 = client.get("/api/monitoring/fallback_plot", params={"name": first})
        assert res2.status_code == 200
        # content-type should be PNG
        ct = res2.headers.get("content-type", "")
        assert "png" in ct
