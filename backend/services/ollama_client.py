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
import subprocess
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self):
        self._client = None
        self._has_ollama = False
        self._base_url = os.environ.get("OLLAMA_URL")
        self._api_key = os.environ.get("OLLAMA_CLOUD_API_KEY") or os.environ.get(
            "OLLAMA_API_KEY"
        )
        # If API key present and no explicit URL, prefer cloud base
        if self._api_key and not self._base_url:
            self._base_url = "https://api.ollama.com"
        if not self._base_url:
            self._base_url = "http://localhost:11434"

        try:
            # try to import the official library; API surface may vary by version
            import ollama as _ollama  # type: ignore

            # prefer Ollama class if present
            OllamaClass = getattr(_ollama, "Ollama", None) or getattr(
                _ollama, "Client", None
            )
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
                if hasattr(self._client, "models"):
                    res = self._client.models()
                    return res
                if hasattr(self._client, "list_models"):
                    return self._client.list_models()
            except Exception as e:
                logger.debug("ollama client list_models failed: %s", e)

        # HTTP fallback
        try:
            import requests

            base = self._base_url.rstrip("/")
            # prefer /v1 endpoints for local hosts; Ollama Cloud uses /api/
            if "ollama.com" in base:
                url = base + "/api/tags"
            elif self._api_key or any(
                h in base for h in ("localhost", "127.0.0.1", "0.0.0.0")
            ):
                url = base + "/v1/models"
            else:
                url = base + "/api/models"
            headers = {}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            resp = requests.get(
                url,
                headers=headers or None,
                timeout=float(os.environ.get("OLLAMA_TIMEOUT", "10")),
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.debug("Ollama list_models http fallback failed: %s", e)
        return None

    def generate(
        self,
        model: Optional[str],
        prompt: str,
        stream: bool = False,
        timeout: float = 10.0,
        response_format: Optional[str] = None,
        tools: Optional[list] = None,
    ) -> Optional[Any]:
        """Generate text for `prompt` using `model`.

        - If `stream` is True and the client supports streaming, attempts stream consumption.
        - Returns the joined text output or None on any failure.
        """
        # Try official client first
        if self._has_ollama and self._client is not None:
            try:
                # Common method: generate / chat / completion
                if hasattr(self._client, "generate"):
                    try:
                        # some clients expect model + input/prompt
                        kwargs: Dict[str, Any] = {}
                        if model:
                            kwargs["model"] = model
                        # prefer `input` per cloud docs
                        kwargs["input"] = prompt
                        kwargs["stream"] = stream
                        # pass tools if provided (newer client versions support tool-calling)
                        if tools is not None:
                            try:
                                kwargs["tools"] = tools
                            except Exception:
                                pass
                        # support passing format/response_format to the official client
                        if response_format is not None:
                            # different client versions may expect `format` or `response_format`
                            try:
                                kwargs["format"] = response_format
                            except Exception:
                                kwargs["response_format"] = response_format
                        out = self._client.generate(**kwargs)
                        # try to coerce to string
                        # if the client returned a dict/object and JSON was requested, return it directly
                        if response_format == "json" and isinstance(out, (dict, list)):
                            return out
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

                if hasattr(self._client, "chat"):
                    try:
                        out = self._client.chat(
                            model=model,
                            messages=[{"role": "user", "content": prompt}],
                            stream=stream,
                        )
                        return str(out)
                    except Exception:
                        pass
            except Exception as e:
                logger.debug("ollama client generate failed: %s", e)

        # HTTP fallback
        try:
            import requests

            base = self._base_url.rstrip("/")
            # Ollama Cloud uses /api/chat; local servers typically expose /v1/generate
            if "ollama.com" in base:
                api_path = base + "/api/chat"
            elif self._api_key or any(
                h in base for h in ("localhost", "127.0.0.1", "0.0.0.0")
            ):
                api_path = base + "/v1/generate"
            else:
                api_path = base + "/api/generate"
            headers = {}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            # Chat-style payload for cloud API
            if "ollama.com" in base:
                payload = {
                    "model": model or os.environ.get("OLLAMA_DEFAULT_MODEL"),
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": stream,
                }
            else:
                payload: Dict[str, Any] = {"input": prompt, "prompt": prompt}
                if model:
                    payload["model"] = model
            # propagate requested response format into payload when supported
            if response_format:
                # common parameter name is 'format' for many Ollama APIs
                payload["format"] = response_format
            # include tools in payload when provided (HTTP fallback)
            if tools is not None:
                try:
                    payload["tools"] = tools
                except Exception:
                    pass
            try:
                payload["max_tokens"] = int(os.environ.get("OLLAMA_MAX_TOKENS", "200"))
            except Exception:
                pass
            try:
                payload["temperature"] = float(
                    os.environ.get("OLLAMA_TEMPERATURE", "0.0")
                )
            except Exception:
                pass

            if stream:
                return self._http_generate_stream(api_path, payload, headers, timeout)

            resp = requests.post(api_path, json=payload, headers=headers or None, timeout=timeout)
            resp.raise_for_status()
            return self._parse_http_response(resp, response_format)
        except Exception as e:
            logger.debug("Ollama HTTP generate failed: %s", e)
        return None

    def _http_generate_stream(self, api_path: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: float) -> Optional[str]:
        import requests

        resp = requests.post(api_path, json=payload, headers=headers or None, timeout=timeout, stream=True)
        resp.raise_for_status()
        parts: list[str] = []
        for raw in resp.iter_lines(decode_unicode=True):
            if not raw:
                continue
            line = raw.strip()
            if line.startswith("data:"):
                line = line[len("data:") :].strip()
            if line == "[DONE]":
                break
            try:
                j = json.loads(line)
                if isinstance(j, dict):
                    if "content" in j:
                        parts.append(str(j.get("content") or ""))
                    elif "text" in j:
                        parts.append(str(j.get("text") or ""))
                    else:
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
        return "\n".join([p for p in parts if p]) or None

    def _parse_http_response(self, resp, response_format: Optional[str]) -> Optional[Any]:
        # Prefer returning JSON when explicitly requested
        data = None
        if response_format == "json":
            try:
                return resp.json()
            except Exception:
                data = None

        try:
            data = resp.json()
        except Exception:
            data = None

        if isinstance(data, (dict, list)):
            if isinstance(data, dict) and "outputs" in data and isinstance(data["outputs"], list):
                out0 = data["outputs"][0]
                if isinstance(out0, dict):
                    return out0.get("content") or out0.get("text") or json.dumps(out0)
                return str(out0)
            if isinstance(data, dict) and "output" in data and isinstance(data["output"], list):
                pieces = []
                for it in data["output"]:
                    if isinstance(it, dict):
                        pieces.append(it.get("content") or it.get("text") or "")
                    elif isinstance(it, str):
                        pieces.append(it)
                return "\n".join(pieces).strip()
            if isinstance(data, dict) and "text" in data:
                return data.get("text")

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

        if resp.text:
            return resp.text
        return None

    def embeddings(
        self, model: Optional[str], input: str, timeout: float = 10.0
    ) -> Optional[list]:
        """Return embeddings for `input` using the underlying client or HTTP fallback.

        Returns a list of floats (single vector) on success or None on failure.
        """
        # Try official client first
        if self._has_ollama and self._client is not None:
            try:
                # many clients expose an `embeddings` or `embed` method
                if hasattr(self._client, "embeddings"):
                    try:
                        out = self._client.embeddings(model=model, input=input)
                        return out
                    except TypeError:
                        try:
                            out = self._client.embeddings(input)
                            return out
                        except Exception:
                            pass
                if hasattr(self._client, "embed"):
                    try:
                        out = self._client.embed(model=model, input=input)
                        return out
                    except Exception:
                        try:
                            out = self._client.embed(input)
                            return out
                        except Exception:
                            pass
            except Exception as e:
                logger.debug("ollama client embeddings failed: %s", e)

        # HTTP fallback: try multiple common endpoints (per Ollama docs use /api/embed)
        try:
            import requests

            base = self._base_url.rstrip("/")
            endpoints = []
            # prefer documented cloud path /api/embed
            endpoints.append(base + "/api/embed")
            # fallback variants
            endpoints.append(base + "/api/embeddings")
            endpoints.append(base + "/v1/embeddings")

            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            # prepare candidate models: prioritized list (explicit model first)
            env_candidates = os.environ.get("OLLAMA_EMBEDDING_CANDIDATES", "")
            defaults = ["embeddinggemma", "qwen3-embedding", "all-minilm"]
            candidates = []
            if model:
                candidates.append(model)
            if env_candidates:
                for m in [m.strip() for m in env_candidates.split(",") if m.strip()]:
                    if m not in candidates:
                        candidates.append(m)
            for d in defaults:
                if d not in candidates:
                    candidates.append(d)

            def _make_payload(m):
                return {
                    "model": m or os.environ.get("OLLAMA_DEFAULT_MODEL"),
                    "input": input,
                }

            def _extract_vector(data):
                # common shapes: {"embeddings": [[...]]} or {"data": [{"embedding": [...]}, ...]} or {"embedding": [...]} or list
                if data is None:
                    return None
                if isinstance(data, dict):
                    if (
                        "embeddings" in data
                        and isinstance(data["embeddings"], list)
                        and data["embeddings"]
                    ):
                        first = data["embeddings"][0]
                        if isinstance(first, list):
                            return first
                    if (
                        "data" in data
                        and isinstance(data["data"], list)
                        and data["data"]
                    ):
                        first = data["data"][0]
                        if isinstance(first, dict) and "embedding" in first:
                            return first["embedding"]
                    if "embedding" in data and isinstance(data["embedding"], list):
                        return data["embedding"]
                if isinstance(data, list) and data and isinstance(data[0], list):
                    return data[0]

                # deep search for any numeric vector
                def _find_vector(obj):
                    if (
                        isinstance(obj, list)
                        and obj
                        and all(isinstance(x, (int, float)) for x in obj)
                    ):
                        return obj
                    if isinstance(obj, dict):
                        for v in obj.values():
                            r = _find_vector(v)
                            if r:
                                return r
                    if isinstance(obj, list):
                        for v in obj:
                            r = _find_vector(v)
                            if r:
                                return r
                    return None

                return _find_vector(data)

            # try each candidate model until we get an embedding
            for m in candidates:
                payload = _make_payload(m)
                for api_path in endpoints:
                    try:
                        resp = requests.post(
                            api_path, json=payload, headers=headers, timeout=timeout
                        )
                        # do not raise_for_status here; we want to inspect body for model-not-found
                    except Exception:
                        # try next endpoint
                        continue

                    data = None
                    try:
                        data = resp.json()
                    except Exception:
                        data = None

                    vec = _extract_vector(data)
                    if vec:
                        logger.debug(
                            "ollama_client.embeddings: got embedding using model=%s, endpoint=%s",
                            m,
                            api_path,
                        )
                        return vec

                    # detect model-not-found hints and continue to next model candidate
                    try:
                        if isinstance(data, dict):
                            # common error shapes
                            err = (
                                data.get("error")
                                or data.get("message")
                                or data.get("error_message")
                                or data.get("detail")
                            )
                            if (
                                err
                                and isinstance(err, str)
                                and "model" in err
                                and "not found" in err
                            ):
                                logger.debug(
                                    "ollama_client.embeddings: model %s not found at %s; trying next candidate",
                                    m,
                                    api_path,
                                )
                                # If configured, attempt an opt-in auto-pull of the missing model
                                allow_auto = os.environ.get(
                                    "OLLAMA_ALLOW_AUTO_PULL", ""
                                ).lower()
                                if allow_auto in ("1", "true", "yes"):
                                    try:
                                        pull_cmd = os.environ.get(
                                            "OLLAMA_PULL_CMD", "ollama"
                                        )
                                        pull_timeout = int(
                                            os.environ.get("OLLAMA_PULL_TIMEOUT", "600")
                                        )
                                        logger.info(
                                            "OLLAMA_ALLOW_AUTO_PULL enabled: attempting to pull model %s using %s",
                                            m,
                                            pull_cmd,
                                        )
                                        subprocess.run(
                                            [pull_cmd, "pull", m],
                                            check=True,
                                            timeout=pull_timeout,
                                        )
                                        # try the same endpoint once more after pulling
                                        try:
                                            resp2 = requests.post(
                                                api_path,
                                                json=payload,
                                                headers=headers,
                                                timeout=timeout,
                                            )
                                            try:
                                                data2 = resp2.json()
                                            except Exception:
                                                data2 = None
                                            vec2 = _extract_vector(data2)
                                            if vec2:
                                                logger.info(
                                                    "ollama_client.embeddings: pulled model %s and retrieved embedding",
                                                    m,
                                                )
                                                return vec2
                                        except Exception:
                                            logger.debug(
                                                "ollama_client.embeddings: pull succeeded but second request failed for model %s",
                                                m,
                                            )
                                    except Exception as e:
                                        logger.debug(
                                            "ollama_client.embeddings: auto-pull failed for model %s: %s",
                                            m,
                                            e,
                                        )
                                continue
                            # nested shape: {"error": {"message": "model \"...\" not found"}}
                            if isinstance(err, dict):
                                msg = err.get("message")
                                if msg and "not found" in msg:
                                    logger.debug(
                                        "ollama_client.embeddings: model %s not found (nested error); trying next candidate",
                                        m,
                                    )
                                    allow_auto = os.environ.get(
                                        "OLLAMA_ALLOW_AUTO_PULL", ""
                                    ).lower()
                                    if allow_auto in ("1", "true", "yes"):
                                        try:
                                            pull_cmd = os.environ.get(
                                                "OLLAMA_PULL_CMD", "ollama"
                                            )
                                            pull_timeout = int(
                                                os.environ.get(
                                                    "OLLAMA_PULL_TIMEOUT", "600"
                                                )
                                            )
                                            logger.info(
                                                "OLLAMA_ALLOW_AUTO_PULL enabled: attempting to pull model %s using %s",
                                                m,
                                                pull_cmd,
                                            )
                                            subprocess.run(
                                                [pull_cmd, "pull", m],
                                                check=True,
                                                timeout=pull_timeout,
                                            )
                                            try:
                                                resp2 = requests.post(
                                                    api_path,
                                                    json=payload,
                                                    headers=headers,
                                                    timeout=timeout,
                                                )
                                                try:
                                                    data2 = resp2.json()
                                                except Exception:
                                                    data2 = None
                                                vec2 = _extract_vector(data2)
                                                if vec2:
                                                    logger.info(
                                                        "ollama_client.embeddings: pulled model %s and retrieved embedding",
                                                        m,
                                                    )
                                                    return vec2
                                            except Exception:
                                                logger.debug(
                                                    "ollama_client.embeddings: pull succeeded but second request failed for model %s",
                                                    m,
                                                )
                                        except Exception as e:
                                            logger.debug(
                                                "ollama_client.embeddings: auto-pull failed for model %s: %s",
                                                m,
                                                e,
                                            )
                                    continue
                    except Exception:
                        pass

        except Exception as e:
            logger.debug("Ollama embeddings http fallback failed: %s", e)
        return None


_default_client: Optional[OllamaClient] = None


def get_default_client() -> OllamaClient:
    global _default_client
    if _default_client is None:
        _default_client = OllamaClient()
    return _default_client


__all__ = ["OllamaClient", "get_default_client"]
