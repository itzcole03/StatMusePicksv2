"""Simple web search tool used as a callable tool by the LLM.

Behaviour:
- If `BING_API_KEY` env var is set, performs a Bing Web Search request and
  returns concatenated top snippet results.
- Otherwise returns a deterministic stub indicating no live search is
  configured (useful for tests and CI).
"""
from __future__ import annotations

import os
import logging
from typing import List
import time
import re

logger = logging.getLogger(__name__)

# Simple in-process rate limiter for web_search calls (best-effort)
_ws_bucket = {'tokens': 0.0, 'last': 0.0}
_WS_RATE_RPM = int(os.environ.get('WEB_SEARCH_MAX_RPM', '60'))


def _consume_web_search_token(amount: int = 1) -> bool:
    now = time.time()
    # Try to use Redis-backed token bucket in production when available
    try:
        from backend.services.cache import get_sync_redis

        r = get_sync_redis()
        if r is not None:
            # Lua token-bucket: KEYS[1]=key, ARGV[1]=now, ARGV[2]=rate_per_minute, ARGV[3]=amount
            lua = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local req = tonumber(ARGV[3])
local data = redis.call('HMGET', key, 'tokens', 'last')
local tokens = tonumber(data[1])
local last = tonumber(data[2])
if tokens == nil then
  tokens = rate
  last = now
end
local elapsed = now - last
local refill = elapsed * (rate / 60.0)
tokens = math.min(rate, tokens + refill)
if tokens >= req then
  tokens = tokens - req
  redis.call('HMSET', key, 'tokens', tostring(tokens), 'last', tostring(now))
  redis.call('EXPIRE', key, 120)
  return 1
else
  redis.call('HMSET', key, 'tokens', tostring(tokens), 'last', tostring(now))
  redis.call('EXPIRE', key, 120)
  return 0
end
"""
            key = 'web_search_rate_bucket'
            try:
                allowed = r.eval(lua, 1, key, now, _WS_RATE_RPM, amount)
                return bool(int(allowed))
            except Exception:
                # Fall back to local bucket if Redis eval fails
                pass
    except Exception:
        # import/get_sync_redis not available or failed; fall back
        pass

    # Fallback: in-process bucket
    bucket = _ws_bucket
    if bucket['last'] == 0.0:
        bucket['tokens'] = float(_WS_RATE_RPM)
        bucket['last'] = now

    elapsed = now - bucket['last']
    refill = elapsed * (_WS_RATE_RPM / 60.0)
    bucket['tokens'] = min(float(_WS_RATE_RPM), bucket['tokens'] + refill)
    bucket['last'] = now

    if bucket['tokens'] >= amount:
        bucket['tokens'] -= amount
        return True
    return False


def _sanitize_query(q: str, max_len: int = 300) -> str:
    if not q:
        return ''
    # remove control chars
    q = re.sub(r"[\x00-\x1f\x7f]+", ' ', q)
    q = q.strip()
    if len(q) > max_len:
        q = q[:max_len]
    # collapse whitespace
    q = re.sub(r"\s+", ' ', q)
    return q


def _bing_search(query: str, count: int = 3) -> str:
    try:
        import requests
    except Exception:
        logger.debug("requests not available for web search")
        q = _sanitize_query(query)
        return f"[web_search disabled: requests not installed] {q}"

    key = os.environ.get('BING_API_KEY')
    if not key:
        return f"[web_search not configured] {query}"

    headers = {'Ocp-Apim-Subscription-Key': key}
    params = {'q': query, 'count': str(count)}
    try:
        resp = requests.get('https://api.bing.microsoft.com/v7.0/search', headers=headers, params=params, timeout=5)
        resp.raise_for_status()
        j = resp.json()
        snippets: List[str] = []
        # gather top webPages snippets
        web = j.get('webPages', {}).get('value', [])
        for item in web[:count]:
            title = item.get('name') or ''
            snippet = item.get('snippet') or item.get('snippet') or ''
            url = item.get('url') or ''
            snippets.append(f"- {title}: {snippet} ({url})")
        if snippets:
            return "\n".join(snippets)
        return f"[bing returned no results] {query}"
    except Exception as e:
        logger.exception("Bing search failed")
        return f"[bing error] {str(e)}"


def web_search(query: str) -> str:
    """Public tool function: returns a short plain-text summary for `query`."""
    # Basic rate limiting and sanitization to protect external APIs and avoid
    # uncontrolled tool usage when called by LLMs.
    try:
        q = _sanitize_query(str(query or ''))
    except Exception:
        q = ''

    if not q:
        return "[web_search invalid query]"

    allowed = _consume_web_search_token(1)
    if not allowed:
        logger.warning('web_search rate limit exceeded')
        return "[web_search rate_limited]"

    # First try DuckDuckGo Instant Answer API (no key required)
    try:
        import requests
        ddg_url = "https://api.duckduckgo.com/"
        params = {"q": q, "format": "json", "no_redirect": 1, "no_html": 1, "skip_disambig": 1}
        resp = requests.get(ddg_url, params=params, timeout=5)
        resp.raise_for_status()
        j = resp.json()
        parts = []
        abstract = j.get("AbstractText") or ""
        if abstract:
            parts.append(abstract)

        # RelatedTopics is often a list of dicts or nested lists
        rt = j.get("RelatedTopics") or []
        count = 0
        for item in rt:
            if isinstance(item, dict):
                text = item.get("Text") or item.get("Result") or ""
                if text:
                    parts.append(text)
                    count += 1
            if count >= 3:
                break

        # If we collected useful parts, return them
        if parts:
            return "\n".join(parts[:5])
    except Exception:
        logger.debug("DuckDuckGo instant answer failed or unavailable, falling back to Bing or stub")

    # Fall back to Bing if API key present, otherwise return deterministic stub
    key = os.environ.get('BING_API_KEY')
    if key:
        return _bing_search(query)
    q = _sanitize_query(query)
    return f"[web_search not configured] {q}"
