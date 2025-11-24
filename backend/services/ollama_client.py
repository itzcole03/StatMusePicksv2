"""Lightweight Ollama client wrapper.

Tries to use the official `ollama` package when available, otherwise falls
back to a tiny HTTP client using `requests` against the Ollama Cloud or
local server. Provides two convenience functions used by other services:
- `list_models()` -> list available models
- `generate(model, prompt, stream=False, timeout=10)` -> returns text or None

Environment variables:
- `OLLAMA_CLOUD_API_KEY` or `OLLAMA_API_KEY` to use Ollama Cloud with Bearer auth
- `OLLAMA_URL` to override base URL (default local `http://localhost:11434` or cloud `https://api.ollama.com` when key present)
- `OLLAMA_TIMEOUT` request timeout seconds
"""
from __future__ import annotations
import json
import logging
import os
from typing import Optional, Any, Dict

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self):
        self._client = None
        self._has_ollama = False
        self._base_url = os.environ.get('OLLAMA_URL')
        self._api_key = os.environ.get('OLLAMA_CLOUD_API_KEY') or os.environ.get('OLLAMA_API_KEY')
        # If API key present and no explicit URL, prefer cloud base
        if self._api_key and not self._base_url:
            self._base_url = 'https://api.ollama.com'
        if not self._base_url:
            self._base_url = 'http://localhost:11434'

        try:
            # try to import the official library; API surface may vary by version
            import ollama as _ollama  # type: ignore
            # prefer Ollama class if present
            OllamaClass = getattr(_ollama, 'Ollama', None) or getattr(_ollama, 'Client', None)
            if OllamaClass:
                try:
                    # instantiate with api_key if supported
                    self._client = OllamaClass(base_url=self._base_url, api_key=self._api_key)  # type: ignore
                except Exception:
                    # try without args
                    try:
                        self._client = OllamaClass()
                    except Exception:
                        self._client = None
                self._has_ollama = True if self._client is not None else False
        except Exception:
            self._has_ollama = False

    def list_models(self) -> Optional[Any]:
        """Return available models; JSON-like list or None on failure."""
        # Prefer official client
        if self._has_ollama and self._client is not None:
            try:
                # try common method names
                if hasattr(self._client, 'models'):
                    res = self._client.models()
                    return res
                if hasattr(self._client, 'list_models'):
                    return self._client.list_models()
            except Exception as e:
                logger.debug("ollama client list_models failed: %s", e)

        # HTTP fallback
        try:
            import requests

            url = self._base_url.rstrip('/') + '/v1/models' if self._api_key else self._base_url.rstrip('/') + '/api/models'
            headers = {}
            if self._api_key:
                headers['Authorization'] = f"Bearer {self._api_key}"
            resp = requests.get(url, headers=headers or None, timeout=float(os.environ.get('OLLAMA_TIMEOUT', '10')))
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.debug("Ollama list_models http fallback failed: %s", e)
        return None

    def generate(self, model: Optional[str], prompt: str, stream: bool = False, timeout: float = 10.0) -> Optional[str]:
        """Generate text for `prompt` using `model`.

        - If `stream` is True and the client supports streaming, attempts stream consumption.
        - Returns the joined text output or None on any failure.
        """
        # Try official client first
        if self._has_ollama and self._client is not None:
            try:
                # Common method: generate / chat / completion
                if hasattr(self._client, 'generate'):
                    try:
                        # some clients expect model + input/prompt
                        kwargs: Dict[str, Any] = {}
                        if model:
                            kwargs['model'] = model
                        # prefer `input` per cloud docs
                        kwargs['input'] = prompt
                        kwargs['stream'] = stream
                        out = self._client.generate(**kwargs)
                        # try to coerce to string
                        if isinstance(out, str):
                            return out
                        try:
                            return json.dumps(out)
                        except Exception:
                            return str(out)
                    except TypeError:
                        # older API shapes: generate(model, prompt)
                        out = self._client.generate(model, prompt)
                        return str(out)

                if hasattr(self._client, 'chat'):
                    try:
                        out = self._client.chat(model=model, messages=[{"role": "user", "content": prompt}], stream=stream)
                        return str(out)
                    except Exception:
                        pass
            except Exception as e:
                logger.debug("ollama client generate failed: %s", e)

        # HTTP fallback
        try:
            import requests

            api_path = self._base_url.rstrip('/') + '/v1/generate' if self._api_key else self._base_url.rstrip('/') + '/api/generate'
            headers = {}
            if self._api_key:
                headers['Authorization'] = f"Bearer {self._api_key}"
            payload: Dict[str, Any] = {"input": prompt, "prompt": prompt}
            if model:
                payload['model'] = model
            try:
                payload['max_tokens'] = int(os.environ.get('OLLAMA_MAX_TOKENS', '200'))
            except Exception:
                pass
            try:
                payload['temperature'] = float(os.environ.get('OLLAMA_TEMPERATURE', '0.0'))
            except Exception:
                pass

            if stream:
                resp = requests.post(api_path, json=payload, headers=headers or None, timeout=timeout, stream=True)
                resp.raise_for_status()
                parts = []
                for raw in resp.iter_lines(decode_unicode=True):
                    if not raw:
                        continue
                    line = raw.strip()
                    if line.startswith('data:'):
                        line = line[len('data:'):].strip()
                    if line == '[DONE]':
                        break
                    try:
                        j = json.loads(line)
                        # attempt to extract common fields
                        if isinstance(j, dict):
                            if 'content' in j:
                                parts.append(str(j.get('content') or ''))
                            elif 'text' in j:
                                parts.append(str(j.get('text') or ''))
                            else:
                                # search nested
                                def _find_text(obj):
                                    if isinstance(obj, str):
                                        return obj
                                    if isinstance(obj, dict):
                                        for v in obj.values():
                                            t = _find_text(v)
                                            if t:
                                                return t
                                    if isinstance(obj, list):
                                        for v in obj:
                                            t = _find_text(v)
                                            if t:
                                                return t
                                    return None
                                t = _find_text(j)
                                if t:
                                    parts.append(t)
                        else:
                            parts.append(str(j))
                    except Exception:
                        parts.append(line)
                return '\n'.join([p for p in parts if p]) or None

            resp = requests.post(api_path, json=payload, headers=headers or None, timeout=timeout)
            resp.raise_for_status()
            # parse JSON if available
            try:
                data = resp.json()
            except Exception:
                data = None
            if isinstance(data, dict):
                # common shapes
                if 'outputs' in data and isinstance(data['outputs'], list):
                    out0 = data['outputs'][0]
                    if isinstance(out0, dict):
                        return out0.get('content') or out0.get('text') or json.dumps(out0)
                    return str(out0)
                if 'output' in data and isinstance(data['output'], list):
                    pieces = []
                    for it in data['output']:
                        if isinstance(it, dict):
                            pieces.append(it.get('content') or it.get('text') or '')
                        elif isinstance(it, str):
                            pieces.append(it)
                    return '\n'.join(pieces).strip()
                if 'text' in data:
                    return data.get('text')
                # fallback: find any string
                def _find_text(obj):
                    if isinstance(obj, str):
                        return obj
                    if isinstance(obj, dict):
                        for v in obj.values():
                            t = _find_text(v)
                            if t:
                                return t
                    if isinstance(obj, list):
                        for v in obj:
                            t = _find_text(v)
                            if t:
                                return t
                    return None
                t = _find_text(data)
                if t:
                    return t
            # if not JSON return text body
            if resp.text:
                return resp.text
        except Exception as e:
            logger.debug("Ollama HTTP generate failed: %s", e)
        return None


_default_client: Optional[OllamaClient] = None


def get_default_client() -> OllamaClient:
    global _default_client
    if _default_client is None:
        _default_client = OllamaClient()
    return _default_client


__all__ = ["OllamaClient", "get_default_client"]
