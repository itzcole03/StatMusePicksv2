import json
import os
import sys
import pytest

# Ensure repo root is on sys.path so `backend` package imports work in pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.services.llm_feature_service import LLMFeatureService


class MockStreamResp:
    def __init__(self, lines):
        self._lines = lines
        self.headers = {"Content-Type": "text/event-stream"}
        self.text = ""

    def iter_lines(self, decode_unicode=True):
        for l in self._lines:
            yield l

    def raise_for_status(self):
        return None

    def json(self):
        return {}


class MockJSONResp:
    def __init__(self, data):
        self._data = data
        self.headers = {"Content-Type": "application/json"}
        self.text = json.dumps(data)

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


def test_streaming_parsing(monkeypatch):
    os.environ['OLLAMA_STREAM'] = 'true'
    os.environ['OLLAMA_CLOUD_API_KEY'] = 'fakekey'
    os.environ['OLLAMA_URL'] = 'https://api.ollama.com'

    svc = LLMFeatureService()

    lines = [
        'data: {"content":"injury: player injured"}\n',
        'data: {"content":"morale: high"}\n',
        'data: [DONE]\n',
    ]

    def fake_post(url, json=None, headers=None, timeout=None, stream=False):
        assert stream is True
        return MockStreamResp(lines)

    # Patch the global requests.post used by the service at call time
    monkeypatch.setattr('requests.post', fake_post)

    out = svc._ollama_request_with_retries("prompt", max_attempts=1)
    assert out is not None
    assert "injury: player injured" in out
    assert "morale: high" in out


def test_json_parsing(monkeypatch):
    os.environ.pop('OLLAMA_STREAM', None)
    os.environ['OLLAMA_CLOUD_API_KEY'] = 'fakekey'
    os.environ['OLLAMA_URL'] = 'https://api.ollama.com'

    svc = LLMFeatureService()
    data = {"outputs": [{"content": "Player is confident and healthy"}]}

    def fake_post(url, json=None, headers=None, timeout=None, stream=False):
        return MockJSONResp(data)

    # Patch the global requests.post used by the service at call time
    monkeypatch.setattr('requests.post', fake_post)

    out = svc._ollama_request_with_retries("prompt", max_attempts=1)
    assert out is not None
    assert "confident and healthy" in out
