from fastapi.testclient import TestClient
import os

from backend.main import app


def test_training_summary_endpoint():
    # Point the endpoint at the sample training summary included in tests
    os.environ["TRAINING_SUMMARY_PATH"] = "backend/tests/data/sample_training_summary.json"
    client = TestClient(app)
    res = client.get("/api/monitoring/training_summary")
    assert res.status_code == 200
    data = res.json()
    assert data.get("ok") is True
    agg = data.get("aggregates")
    assert isinstance(agg, dict)
    # basic keys expected from aggregate_training_summary
    assert "avg_pct_with_last5" in agg
    assert "n_players" in agg
