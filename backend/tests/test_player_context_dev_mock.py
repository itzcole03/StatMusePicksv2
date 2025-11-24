from fastapi.testclient import TestClient
from backend.main import app


def test_player_context_dev_mock_env(monkeypatch, tmp_path, capsys):
    # Ensure DEV_MOCK_CONTEXT produces a sample recentGames payload when no real data
    import os
    os.environ['DEV_MOCK_CONTEXT'] = '1'

    client = TestClient(app)
    resp = client.get('/api/player_context?player=Test+Player&limit=3')
    assert resp.status_code == 200
    data = resp.json()
    assert data['player'] == 'Test Player'
    assert isinstance(data.get('recentGames'), list)
    assert len(data['recentGames']) == 3
    assert 'rollingAverages' in data
    assert isinstance(data['rollingAverages'], dict)

    # cleanup
    del os.environ['DEV_MOCK_CONTEXT']
