import os
import pytest
from fastapi.testclient import TestClient
from backend.main import app


# Integration test that exercises the real NBA data path.
# This test is skipped by default to avoid flaky network calls.
# To run locally (with network access and any required API keys):
#
# RUN_LIVE_NBA_TESTS=1 pytest backend/tests/test_player_context_integration.py -q


if os.environ.get("RUN_LIVE_NBA_TESTS") != "1":
    pytest.skip("Skipping live NBA integration tests. Set RUN_LIVE_NBA_TESTS=1 to run.", allow_module_level=True)


def test_player_context_live_fetch():
    client = TestClient(app)
    # Pick an active player likely to have recent games
    resp = client.get('/api/player_context?player=Stephen%20Curry&stat=points&limit=5')
    assert resp.status_code == 200
    data = resp.json()
    # Expect recentGames to be a list with at least one entry when live data is available
    assert isinstance(data.get('recentGames'), list)
    assert len(data.get('recentGames', [])) > 0
    # rollingAverages should be present (may be zero if feature engine cannot compute)
    assert 'rollingAverages' in data
