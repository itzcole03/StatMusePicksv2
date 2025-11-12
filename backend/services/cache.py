from __future__ import annotations

"""Redis-backed async cache with an in-memory fallback for local dev/tests.

Usage:
  from backend.services.cache import redis_get_json, redis_set_json

Set `REDIS_URL` to your Redis instance. If not set or redis is unavailable,
the module will use a simple in-memory dict with TTL semantics.
"""

import os
import json
import asyncio
from typing import Any, Optional

try:
    import redis.asyncio as aioredis  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    aioredis = None  # type: ignore

_redis_client: Optional["aioredis.Redis"] = None
_fallback_store: dict[str, dict] = {}
_fallback_lock = asyncio.Lock()


def get_redis() -> Optional["aioredis.Redis"]:
    """Return a singleton Redis client or None if not configured/available."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    url = os.environ.get("REDIS_URL")
    if not url or aioredis is None:
        return None

    _redis_client = aioredis.from_url(url, decode_responses=True)
    return _redis_client


async def redis_set_json(key: str, obj: Any, ex: Optional[int] = None) -> bool:
    """Store JSON-serializable `obj` at `key`. Optional expiry `ex` in seconds."""
    client = get_redis()
    if client is None:
        async with _fallback_lock:
            _fallback_store[key] = {"v": json.dumps(obj), "e": None}
            if ex:
                _fallback_store[key]["e"] = asyncio.get_event_loop().time() + ex
        return True

    try:
        await client.set(key, json.dumps(obj), ex=ex)
        return True
    except Exception:
        return False


async def redis_get_json(key: str) -> Optional[Any]:
    """Retrieve JSON object stored at `key`, or None if missing/expired."""
    client = get_redis()
    if client is None:
        async with _fallback_lock:
            item = _fallback_store.get(key)
            if not item:
                return None
            if item.get("e") and asyncio.get_event_loop().time() > item["e"]:
                del _fallback_store[key]
                return None
            try:
                return json.loads(item["v"])
            except Exception:
                return None

    try:
        raw = await client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        return None


async def redis_delete(key: str) -> bool:
    client = get_redis()
    if client is None:
        async with _fallback_lock:
            if key in _fallback_store:
                del _fallback_store[key]
                return True
            return False

    try:
        await client.delete(key)
        return True
    except Exception:
        return False


async def close_redis() -> None:
    """Close the async redis client if initialized."""
    global _redis_client
    if _redis_client is None:
        return
    try:
        await _redis_client.close()
    except Exception:
        pass
    _redis_client = None
