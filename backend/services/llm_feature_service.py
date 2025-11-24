"""LLM-based qualitative feature extraction service.

This is a lightweight scaffold that fetches text (news/summaries) and
extracts simple numeric signals that can be included as model features.
It uses a pluggable LLM client (not included) and a Redis cache + in-process
fallback to keep calls idempotent and cheap.
"""
from __future__ import annotations
import hashlib
import json
import logging
import os
from typing import Optional, Dict
import time
import re
import random

logger = logging.getLogger(__name__)

# Keep a tiny in-process fallback cache for dev when Redis is unavailable
_fallback_cache: Dict[str, Dict] = {}


class LLMFeatureService:
    def __init__(self, redis_client: Optional[object] = None, ttl_seconds: int = 24 * 3600):
        self.redis = redis_client
        self.ttl = int(ttl_seconds)

    def _cache_key(self, player_name: str, source_id: str) -> str:
        key_raw = f"llm_feat:{player_name}:{source_id}"
        return hashlib.sha1(key_raw.encode("utf-8")).hexdigest()

    def _get_cached(self, key: str) -> Optional[Dict]:
        if self.redis:
            try:
                v = self.redis.get(key)
                if v:
                    return json.loads(v)
            except Exception:
                logger.exception("Redis read failed for %s", key)
        return _fallback_cache.get(key)

    def _set_cached(self, key: str, value: Dict) -> None:
        if self.redis:
            try:
                self.redis.set(key, json.dumps(value), ex=self.ttl)
                return
            except Exception:
                logger.exception("Redis write failed for %s", key)
        _fallback_cache[key] = value

    def _openai_request_with_retries(self, prompt: str, max_attempts: int = 3, backoff_factor: float = 1.0) -> Optional[str]:
        """Call OpenAI Completion API with simple retry/backoff and return text or None.

        Keeps the call lazy-imported so environments without `openai` don't fail.
        """
        try:
            import openai
        except Exception:
            logger.debug("openai package not installed; skipping provider")
            return None

        # set API key if provided in env to support direct library use
        if os.environ.get('OPENAI_API_KEY'):
            try:
                openai.api_key = os.environ.get('OPENAI_API_KEY')
            except Exception:
                logger.debug('Could not set openai.api_key attribute')

        # optional simple throttling (calls per second)
        rate_limit = 0.0
        try:
            rate_limit = float(os.environ.get('OPENAI_RATE_LIMIT_PER_SEC', '0'))
        except Exception:
            rate_limit = 0.0

        # optional cap for exponential backoff wait
        try:
            max_wait = float(os.environ.get('OPENAI_MAX_WAIT_SECONDS', '60'))
        except Exception:
            max_wait = 60.0

        attempts = 0
        while attempts < max_attempts:
            # throttle if configured: ensure minimum interval between calls
            if rate_limit and rate_limit > 0:
                min_interval = 1.0 / rate_limit
                last = getattr(self, '_openai_last_call', 0.0)
                since = time.perf_counter() - last
                if since < min_interval:
                    time.sleep(min_interval - since)
            try:
                # reserve a timestamp for this outgoing call to avoid bursts
                self._openai_last_call = time.perf_counter()
                resp = openai.Completion.create(
                    engine=os.environ.get('OPENAI_ENGINE', 'text-davinci-003'),
                    prompt=prompt,
                    max_tokens=int(os.environ.get('OPENAI_MAX_TOKENS', '200')),
                    temperature=float(os.environ.get('OPENAI_TEMPERATURE', '0.0')),
                )
                if hasattr(resp, 'choices') and resp.choices:
                    return getattr(resp.choices[0], 'text', str(resp))
                return str(resp)
            except Exception as e:
                attempts += 1
                # exponential backoff + decorrelated jitter
                base_wait = backoff_factor * (2 ** (attempts - 1))
                jitter = random.uniform(0, min(1.0, base_wait))
                wait = min(max_wait, base_wait + jitter)
                logger.warning("OpenAI request failed (attempt %s/%s): %s — retrying in %.1fs", attempts, max_attempts, e, wait)
                time.sleep(wait)
        logger.error("OpenAI request failed after %s attempts", max_attempts)
        return None

    def _ollama_request_with_retries(self, prompt: str, max_attempts: int = 3, backoff_factor: float = 1.0) -> Optional[str]:
        """Call a local Ollama server's generate endpoint with retries.

        Configurable via env vars:
        - `OLLAMA_URL` (default `http://localhost:11434`)
        - `OLLAMA_MODEL` (optional)
        - `OLLAMA_MAX_TOKENS`, `OLLAMA_TEMPERATURE`
        """
        try:
            import requests
        except Exception:
            logger.debug("requests package not installed; skipping ollama provider")
            return None

        url = os.environ.get('OLLAMA_URL')
        model = os.environ.get('OLLAMA_MODEL')
        # Detect cloud usage if an API key is provided; default cloud base if not overridden
        cloud_key = os.environ.get('OLLAMA_CLOUD_API_KEY') or os.environ.get('OLLAMA_API_KEY')
        if cloud_key and not url:
            url = os.environ.get('OLLAMA_URL', 'https://api.ollama.com')
        if not url:
            url = 'http://localhost:11434'

        # rate limit / backoff params
        try:
            rate_limit = float(os.environ.get('OLLAMA_RATE_LIMIT_PER_SEC', '0'))
        except Exception:
            rate_limit = 0.0
        try:
            max_wait = float(os.environ.get('OLLAMA_MAX_WAIT_SECONDS', '60'))
        except Exception:
            max_wait = 60.0

        # streaming option: when true, try to consume SSE / line-delimited output
        stream_enabled = os.environ.get('OLLAMA_STREAM', 'false').lower() in ('1', 'true', 'yes')

        attempts = 0
        while attempts < max_attempts:
            if rate_limit and rate_limit > 0:
                min_interval = 1.0 / rate_limit
                last = getattr(self, '_ollama_last_call', 0.0)
                since = time.perf_counter() - last
                if since < min_interval:
                    time.sleep(min_interval - since)
            try:
                self._ollama_last_call = time.perf_counter()

                # Ollama Cloud expects `model` and `input` fields; local may accept `prompt`/`model`.
                payload = {}
                if model:
                    payload['model'] = model
                # primary input key is `input` per cloud docs; include `prompt` for backward compatibility
                payload['input'] = prompt
                payload['prompt'] = prompt

                # optional generation controls
                try:
                    payload['max_tokens'] = int(os.environ.get('OLLAMA_MAX_TOKENS', '200'))
                except Exception:
                    pass
                try:
                    payload['temperature'] = float(os.environ.get('OLLAMA_TEMPERATURE', '0.0'))
                except Exception:
                    pass

                # Choose cloud vs local path and headers
                headers = {}
                if cloud_key:
                    api_path = url.rstrip('/') + '/v1/generate'
                    headers['Authorization'] = f"Bearer {cloud_key}"
                else:
                    api_path = url.rstrip('/') + '/api/generate'

                timeout = float(os.environ.get('OLLAMA_TIMEOUT', '10'))

                # If streaming is enabled, request streaming and attempt to parse SSE/line-delimited JSON
                if stream_enabled:
                    # ask server to stream if supported
                    payload['stream'] = True
                    resp = requests.post(api_path, json=payload, headers=headers or None, timeout=timeout, stream=True)
                    resp.raise_for_status()
                    collected = []
                    # SSE or newline-delimited JSON: iterate lines and extract text segments
                    for raw_line in resp.iter_lines(decode_unicode=True):
                        if raw_line is None:
                            continue
                        line = raw_line.strip()
                        if not line:
                            continue
                        # SSE frames often start with "data:"
                        if line.startswith('data:'):
                            line = line[len('data:'):].strip()
                        if line == '[DONE]':
                            break
                        # try parse JSON chunk
                        try:
                            chunk = json.loads(line)
                        except Exception:
                            # fallback: treat as raw text
                            chunk = line
                        # try to pull content string(s)
                        if isinstance(chunk, str):
                            collected.append(chunk)
                        elif isinstance(chunk, dict):
                            # common keys: 'output', 'outputs', 'content', 'text', 'data'
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
                            elif 'outputs' in chunk and isinstance(chunk['outputs'], list):
                                out0 = chunk['outputs'][0]
                                if isinstance(out0, dict):
                                    collected.append(out0.get('content') or out0.get('text') or '')
                                elif isinstance(out0, str):
                                    collected.append(out0)
                            else:
                                # try to find any nested text
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
                                t = _find_text(chunk)
                                if t:
                                    collected.append(t)
                    if collected:
                        return '\n'.join([c for c in collected if c])
                    # no meaningful stream content, fallthrough to non-stream parse below

                # non-streaming request (default)
                resp = requests.post(api_path, json=payload, headers=headers or None, timeout=timeout)
                resp.raise_for_status()
                # Try to parse as JSON; safe fallback to text
                content_type = resp.headers.get('Content-Type', '')
                data = None
                if 'application/json' in content_type or resp.text.strip().startswith('{') or resp.text.strip().startswith('['):
                    try:
                        data = resp.json()
                    except Exception:
                        data = None

                text = None
                if isinstance(data, dict):
                    # common shapes
                    if 'output' in data and isinstance(data['output'], list):
                        pieces = []
                        for item in data['output']:
                            if isinstance(item, dict):
                                pieces.append(item.get('content') or item.get('text') or '')
                            elif isinstance(item, str):
                                pieces.append(item)
                        text = '\n'.join(pieces).strip()
                    elif 'outputs' in data and isinstance(data['outputs'], list):
                        out = data['outputs'][0]
                        if isinstance(out, dict):
                            text = out.get('content') or out.get('text') or None
                        elif isinstance(out, str):
                            text = out
                    elif 'result' in data and isinstance(data['result'], dict):
                        text = json.dumps(data['result'])
                    elif 'text' in data:
                        text = data.get('text')
                    elif 'generated_text' in data:
                        text = data.get('generated_text')
                # if still nothing, try to find any nested string
                if not text and data is not None:
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
                    text = _find_text(data)

                if text:
                    return text
                # if response wasn't JSON or parsing failed, return plain text body
                if resp.text:
                    return resp.text
                return None
            except KeyboardInterrupt:
                raise
            except Exception as e:
                # If we received an HTTP error with a client status, don't aggressively retry
                try:
                    import requests as _requests
                    if isinstance(e, _requests.exceptions.HTTPError) and getattr(e.response, 'status_code', None) in (400, 401, 403, 404):
                        logger.error("Ollama returned non-retryable HTTP error %s; falling back to heuristics", getattr(e.response, 'status_code', None))
                        return None
                except Exception:
                    pass

                attempts += 1
                base_wait = backoff_factor * (2 ** (attempts - 1))
                jitter = random.uniform(0, min(1.0, base_wait))
                wait = min(max_wait, base_wait + jitter)
                logger.warning("Ollama request failed (attempt %s/%s): %s — retrying in %.1fs", attempts, max_attempts, e, wait)
                time.sleep(wait)
        logger.error("Ollama request failed after %s attempts", max_attempts)
        return None

    def extract_features_from_text(self, player_name: str, text: str) -> Dict[str, float]:
        """Extract numeric features from arbitrary text via an LLM or heuristics.

        For now this is a safe fallback implementation using simple heuristics:
        - `injury_sentiment`: -1..1 where negative indicates injury-related mentions
        - `morale_score`: -1..1 sentiment proxy
        - `motivation`: 0..1 indicator for contract-year/award mentions
        """
        # simple hash-based deterministic placeholder so outputs are stable in dev
        h = int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:8], 16)
        injury = ((h % 200) - 100) / 100.0
        morale = ((h >> 3) % 200 - 100) / 100.0
        motivation = ((h >> 6) % 100) / 100.0
        # coaching change impact proxy: small deterministic value from hash
        coaching = ((h >> 9) % 50) / 50.0

        # keyword-based augmentations: deterministic, explainable heuristics
        lower = (text or "").lower()

        # Injury sentiment: look for injury-related tokens; map to [-1.0, 0]
        injury_keywords = ["injur", "sprain", "strain", "out", "questionable", "doubtful", "fracture", "surgery", "day-to-day"]
        inj_matches = sum(1 for k in injury_keywords if k in lower)
        injury_score = -min(1.0, inj_matches * 0.5) if inj_matches else float(injury)

        # Morale: positive/negative token counts mapped to [-1,1]
        pos = sum(bool(re.search(rf"\b{k}\b", lower)) for k in ("confidence", "morale", "happy", "excited", "motivated", "boost"))
        neg = sum(bool(re.search(rf"\b{k}\b", lower)) for k in ("frustrat", "angry", "disappointed", "demotiv", "quiet"))
        morale_score = 0.0
        if pos or neg:
            morale_score = (pos - neg) / max(1, pos + neg)
        else:
            morale_score = float(morale)

        # Motivation: presence of contractual/rivalry/playoff keywords -> [0,1]
        motiv_keys = ("contract", "contract year", "extension", "rival", "rivalry", "playoff", "trade", "trade rumor", "motivated")
        motiv_matches = sum(1 for k in motiv_keys if k in lower)
        motivation_score = min(1.0, max(0.0, motivation + (motiv_matches * 0.33)))

        return {
            "injury_sentiment": float(max(-1.0, min(1.0, injury_score))),
            "morale_score": float(max(-1.0, min(1.0, morale_score))),
            "motivation": float(max(0.0, min(1.0, motivation_score))),
            "coaching_change_impact": float(max(0.0, min(1.0, coaching))),
        }

    def fetch_news_and_extract(self, player_name: str, source_id: str, text_fetcher) -> Dict[str, float]:
        """Fetch textual context via `text_fetcher(player_name)` and extract features.

        `source_id` is a small string used to version/cache the extraction (eg. 'news_v1').
        `text_fetcher` must be a callable that returns a string (or raises).
        """
        key = self._cache_key(player_name, source_id)
        cached = self._get_cached(key)
        if cached:
            return cached

        try:
            text = text_fetcher(player_name)
        except Exception:
            logger.exception("text_fetcher failed for %s", player_name)
            # return neutral features on failure
            result = {"injury_sentiment": 0.0, "morale_score": 0.0, "motivation": 0.0, "coaching_change_impact": 0.0}
            self._set_cached(key, result)
            return result

        # If an external LLM provider is configured, prefer it for richer signals.
        result = None
        try:
            provider = os.environ.get('LLM_PROVIDER')
            if provider:
                p_lower = provider.lower()
                if p_lower == 'openai' and 'OPENAI_API_KEY' in os.environ:
                    prompt = f"Summarize sentiment and flags for player {player_name}: {text[:6000]}"
                    out = self._openai_request_with_retries(prompt, max_attempts=3, backoff_factor=1.0)
                elif p_lower == 'ollama':
                    prompt = f"Summarize sentiment and flags for player {player_name}: {text[:6000]}"
                    out = self._ollama_request_with_retries(prompt, max_attempts=3, backoff_factor=1.0)
                else:
                    out = None

                if out:
                    try:
                        lower_out = out.lower()
                        injury = -0.5 if 'injury' in lower_out or 'injured' in lower_out else 0.0
                        morale = 0.5 if 'morale' in lower_out or 'confidence' in lower_out else 0.0
                        motivation = 1.0 if 'contract' in lower_out or 'motivat' in lower_out or 'extension' in lower_out else 0.0
                        coaching = 1.0 if 'coaching change' in lower_out or 'coach' in lower_out else 0.0
                        result = {
                            'injury_sentiment': float(injury),
                            'morale_score': float(morale),
                            'motivation': float(motivation),
                            'coaching_change_impact': float(coaching),
                        }
                    except Exception:
                        logger.exception('Failed to parse provider output; falling back to heuristics')
        except Exception:
            logger.exception('Provider selection failed')

        if result is None:
            result = self.extract_features_from_text(player_name, text or "")
        # persist
        try:
            self._set_cached(key, result)
        except Exception:
            logger.exception("Failed to cache llm features for %s", player_name)
        return result


# Helper factory for default usage; in the real app pass a Redis client
def create_default_service():
    redis_url = os.environ.get("REDIS_URL")
    redis_client = None
    if redis_url:
        try:
            import redis as _redis

            redis_client = _redis.from_url(redis_url)
        except Exception:
            logger.exception("Failed to create redis client from REDIS_URL")
    return LLMFeatureService(redis_client=redis_client)
