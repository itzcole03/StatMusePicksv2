import os
from fastapi.testclient import TestClient

from backend.fastapi_nba import app


def test_ollama_stream_mocked():
    # Enable mock streaming to avoid needing real Ollama service
    os.environ['DEV_OLLAMA_MOCK'] = '1'
    client = TestClient(app)

    resp = client.post('/api/ollama_stream', json={'model': 'llama3', 'prompt': 'hello world'})
    assert resp.status_code == 200
    # read the event-stream body as text
    text = resp.content.decode('utf-8')
    assert 'mock' in text or 'Hello' in text
    assert '[DONE]' in text
