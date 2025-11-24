"""LLM-derived qualitative feature extraction service.

Lightweight, single-file implementation that requests structured JSON from
the pluggable LLM client (`backend.services.ollama_client.get_default_client()`)
and validates it with Pydantic. Falls back to simple heuristics on failure.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, ValidationError

from backend.services.ollama_client import get_default_client

logger = logging.getLogger(__name__)


class QualitativeFeatures(BaseModel):
    injury_status: str = Field(..., description="Short label for injury status, e.g. 'questionable', 'out', 'healthy'")
    morale_score: int = Field(..., ge=0, le=100, description="Player morale as integer 0-100")
    news_sentiment: float = Field(..., ge=-1.0, le=1.0, description="Normalized sentiment -1..1")
    trade_sentiment: float = Field(0.0, description="Trade rumor sentiment, -1..1")
    motivation: float = Field(0.0, description="Motivation score 0..1")


class LLMFeatureService:
    def __init__(self, default_model: Optional[str] = None, redis_client: Optional[object] = None, ttl_seconds: int = 24 * 3600):
        self.client = get_default_client()
        self.default_model = default_model or os.environ.get('OLLAMA_DEFAULT_MODEL') or 'llama3'
        # optional Redis client for caching; fall back to in-process cache
        self.redis = redis_client
        self.ttl = int(ttl_seconds)
        self._cache: Dict[str, Dict[str, float]] = {}
        self._ollama_last_call = 0.0

    def _build_prompt(self, player_name: str, text: str) -> str:
        return (
            "You are a sports analyst. Given the following short news summary or context,\n"
            "produce a JSON object only (no extra text) with the keys: injury_status (string), morale_score (int 0-100), news_sentiment (float -1.0..1.0), trade_sentiment (float -1.0..1.0), motivation (float 0.0..1.0).\n"
            "Respond using valid JSON only.\n\nContext:\n"
            f"{text}\n\nReturn JSON."
        )

    def extract_from_text(self, player_name: str, text: str, model: Optional[str] = None, max_attempts: int = 2) -> Dict[str, Any]:
        """Request JSON from the client and return validated features or {}.

        Uses `response_format='json'` when calling the client.generate API and
        accepts dict/list or text containing JSON. On validation failure the
        method will attempt a best-effort coercion and otherwise fall back to
        simple heuristics.
        """
        model = model or self.default_model
        prompt = self._build_prompt(player_name, text)

        for _ in range(max_attempts):
            try:
                resp = self.client.generate(model=model, prompt=prompt, timeout=30, response_format='json')
            except Exception as e:
                logger.debug("LLM client.generate failed: %s", e)
                resp = None

            if not resp:
                continue

            parsed = None
            if isinstance(resp, (dict, list)):
                parsed = resp
            else:
                try:
                    parsed = json.loads(str(resp))
                except Exception:
                    # try to find a JSON object substring
                    try:
                        s = str(resp)
                        start = s.find('{')
                        end = s.rfind('}')
                        if start != -1 and end != -1 and end > start:
                            parsed = json.loads(s[start:end+1])
                    except Exception:
                        parsed = None

            if parsed is None:
                continue

            if isinstance(parsed, list) and parsed:
                if isinstance(parsed[0], dict):
                    parsed = parsed[0]

            if not isinstance(parsed, dict):
                continue

            try:
                vf = QualitativeFeatures.parse_obj(parsed)
                return vf.dict()
            except ValidationError:
                coerced = self._coerce_partial(parsed)
                if coerced:
                    try:
                        vf = QualitativeFeatures.parse_obj(coerced)
                        return vf.dict()
                    except ValidationError:
                        pass
                continue

        # fallback heuristics
        lower = (text or "").lower()
        injury = -0.5 if any(k in lower for k in ('injur', 'sprain', 'strain', 'out', 'questionable', 'doubtful')) else 0.0
        morale = 50 if any(k in lower for k in ('morale', 'confidence', 'motivated')) else 50
        motivation = 1.0 if any(k in lower for k in ('contract', 'extension', 'contract year')) else 0.5
        trade = 0.0
        return {
            'injury_status': 'healthy' if injury == 0.0 else 'questionable',
            'morale_score': int(morale),
            'news_sentiment': float(injury),
            'trade_sentiment': float(trade),
            'motivation': float(motivation),
        }

    def _coerce_partial(self, j: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            out = {
                'injury_status': str(j.get('injury_status') or j.get('injury') or j.get('injuryStatus') or 'healthy'),
                'morale_score': int(float(j.get('morale_score') or j.get('morale') or j.get('moraleScore') or 50)),
                'news_sentiment': float(j.get('news_sentiment') or j.get('sentiment') or 0.0),
                'trade_sentiment': float(j.get('trade_sentiment') or j.get('tradeSentiment') or 0.0),
                'motivation': float(j.get('motivation') or j.get('motivation_score') or 0.5),
            }
            return out
        except Exception:
            return None

    def _cache_key(self, player_name: str, source_id: str) -> str:
        return f"llm_feat:{player_name}:{source_id}"

    def _get_cached(self, key: str) -> Optional[Dict[str, float]]:
        if self.redis:
            try:
                v = self.redis.get(key)
                if v:
                    return json.loads(v)
            except Exception:
                logger.exception("Redis read failed for %s", key)
        return self._cache.get(key)

    def _set_cached(self, key: str, value: Dict[str, float]) -> None:
        if self.redis:
            try:
                self.redis.set(key, json.dumps(value), ex=self.ttl)
                return
            except Exception:
                logger.exception("Redis write failed for %s", key)
        self._cache[key] = value

    def _ollama_request_with_retries(self, prompt: str, max_attempts: int = 3, backoff_factor: float = 1.0) -> Optional[str]:
        """Call Ollama HTTP endpoint with optional streaming and retries.

        This mirrors the helper used in earlier versions and is exercised by
        tests that monkeypatch `requests.post` to return streaming lines.
        """
        try:
            import requests
        except Exception:
            logger.debug("requests not available; skipping ollama provider")
            return None

        url = os.environ.get('OLLAMA_URL')
        api_key = os.environ.get('OLLAMA_CLOUD_API_KEY') or os.environ.get('OLLAMA_API_KEY')
        if api_key and not url:
            url = 'https://api.ollama.com'
        if not url:
            url = 'http://localhost:11434'

        stream_enabled = os.environ.get('OLLAMA_STREAM', 'false').lower() in ('1', 'true', 'yes')

        attempts = 0
        max_wait = float(os.environ.get('OLLAMA_MAX_WAIT_SECONDS', '60'))
        while attempts < max_attempts:
            try:
                base = url.rstrip('/')
                if 'ollama.com' in base:
                    api_path = base + '/api/chat'
                    payload = {"model": self.default_model, "messages": [{"role": "user", "content": prompt}], "stream": stream_enabled}
                else:
                    api_path = base + '/v1/generate'
                    payload = {"input": prompt, "prompt": prompt, "model": self.default_model}

                headers = {}
                if api_key:
                    headers['Authorization'] = f"Bearer {api_key}"

                timeout = float(os.environ.get('OLLAMA_TIMEOUT', '10'))

                if stream_enabled:
                    resp = requests.post(api_path, json=payload, headers=headers or None, timeout=timeout, stream=True)
                    resp.raise_for_status()
                    collected = []
                    for raw_line in resp.iter_lines(decode_unicode=True):
                        if raw_line is None:
                            continue
                        line = raw_line.strip()
                        if not line:
                            continue
                        if line.startswith('data:'):
                            line = line[len('data:'):].strip()
                        if line == '[DONE]':
                            break
                        try:
                            chunk = json.loads(line)
                        except Exception:
                            chunk = line
                        if isinstance(chunk, str):
                            collected.append(chunk)
                        elif isinstance(chunk, dict):
                            if 'content' in chunk:
                                collected.append(str(chunk.get('content') or ''))
                            elif 'text' in chunk:
                                collected.append(str(chunk.get('text') or ''))
                            elif 'output' in chunk and isinstance(chunk['output'], list):
                                for item in chunk['output']:
                                    if isinstance(item, dict):
                                        collected.append(item.get('content') or item.get('text') or '')
                                    elif isinstance(item, str):
                                        collected.append(item)
                    if collected:
                        return '\n'.join([c for c in collected if c])
                    # fallthrough

                resp = requests.post(api_path, json=payload, headers=headers or None, timeout=timeout)
                resp.raise_for_status()
                # prefer JSON when available
                try:
                    data = resp.json()
                except Exception:
                    data = None

                if isinstance(data, dict):
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
                    # find nested text
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
            except Exception as e:
                attempts += 1
                import time, random
                base_wait = backoff_factor * (2 ** (attempts - 1))
                jitter = random.uniform(0, min(1.0, base_wait))
                wait = min(max_wait, base_wait + jitter)
                logger.warning("Ollama request failed (attempt %s/%s): %s — retrying in %.1fs", attempts, max_attempts, e, wait)
                time.sleep(wait)
        logger.error("Ollama request failed after %s attempts", max_attempts)
        return None

    def fetch_news_and_extract(self, player_name: str, source_id: str, text_fetcher) -> Dict[str, float]:
        """Fetch text via `text_fetcher` and return numeric features.

        Uses structured extraction when available; otherwise falls back to
        deterministic heuristics. Results are cached in-process keyed by
        `(player_name, source_id)` to make repeated calls stable for tests.
        """
        key = f"{player_name}::{source_id}"
        if key in self._cache:
            return self._cache[key]

        try:
            text = text_fetcher(player_name)
        except Exception:
            text = ""

        # Try structured extraction first
        structured = {}
        try:
            structured = self.extract_from_text(player_name, text)
        except Exception:
            structured = {}

        if structured:
            # normalize morale_score (schema uses 0-100) to [-1.0, 1.0]
            ms = structured.get('morale_score')
            try:
                msf = float(ms) if ms is not None else 50.0
                morale_norm = max(-1.0, min(1.0, (msf - 50.0) / 50.0))
            except Exception:
                morale_norm = 0.0
            out = {
                'injury_sentiment': float(structured.get('news_sentiment') or 0.0),
                'morale_score': float(morale_norm),
                'motivation': float(structured.get('motivation') or 0.0),
                'coaching_change_impact': 0.0,
            }
            self._cache[key] = out
            return out

        # Deterministic heuristic fallback
        lower = (text or "").lower()
        injury = -1.0 if any(k in lower for k in ('injur', 'sprain', 'strain', 'out', 'questionable', 'doubtful')) else 0.0
        morale = 1.0 if any(k in lower for k in ('morale', 'confidence', 'motivated')) else 0.0
        motivation = 1.0 if any(k in lower for k in ('contract', 'extension', 'contract year')) else 0.0
        coaching = 1.0 if any(k in lower for k in ('coach', 'coaching change', 'coach fired', 'coach hired')) else 0.0

        out = {
            'injury_sentiment': float(injury),
            'morale_score': float(morale),
            'motivation': float(motivation),
            'coaching_change_impact': float(coaching),
        }
        self._cache[key] = out
        return out


_default_llm_service: Optional[LLMFeatureService] = None


def create_default_service(default_model: Optional[str] = None) -> LLMFeatureService:
    global _default_llm_service
    if _default_llm_service is None:
        _default_llm_service = LLMFeatureService(default_model=default_model)
    return _default_llm_service


if __name__ == "__main__":
    svc = create_default_service()
    sample = "Player suffered a minor ankle sprain but is listed as questionable; trade rumors are low; morale seems high."
    print(svc.extract_from_text('Test Player', sample))
