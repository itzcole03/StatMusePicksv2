import json

import types

from backend.services.ollama_client import OllamaClient


class DummyStreamResp:
    def __init__(self, lines):
        self._lines = lines

    def raise_for_status(self):
        return None

    def iter_lines(self, decode_unicode=True):
        for l in self._lines:
            yield l

    @property
    def text(self):
        return "\n".join(self._lines)


class DummyResp:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self._body

    @property
    def text(self):
        return json.dumps(self._body)


def test_http_generate_stream(monkeypatch):
    # simulate SSE-style lines with data: prefix
    lines = [
        'data: {"content": "hello"}',
        'data: {"content": " world"}',
        'data: [DONE]',
    ]

    def fake_post(api_path, json=None, headers=None, timeout=None, stream=False):
        return DummyStreamResp(lines)

    import requests as _requests

    monkeypatch.setattr(_requests, "post", fake_post)

    client = OllamaClient()
    out = client._http_generate_stream("/v1/generate", {"input": "x"}, {}, timeout=1)
    assert out is not None
    assert "hello" in out


def test_parse_http_response_various_shapes():
    client = OllamaClient()

    # outputs list shape
    resp = DummyResp({"outputs": [{"content": "a"}]})
    assert client._parse_http_response(resp, None) == "a"

    # output array shape
    resp = DummyResp({"output": [{"content": "b"}]})
    assert client._parse_http_response(resp, None) == "b"

    # text field
    resp = DummyResp({"text": "c"})
    assert client._parse_http_response(resp, None) == "c"

    # nested find
    resp = DummyResp({"foo": {"bar": "d"}})
    assert client._parse_http_response(resp, None) == "d"
