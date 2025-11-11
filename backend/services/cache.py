"""Simple async Redis cache helper for the backend.

This module exposes `get_redis()` to obtain a singleton Redis client
and convenience `get` / `set_json` helpers used across the app.

It uses `redis.asyncio` (the modern redis-py asyncio client). If
`REDIS_URL` is not set the helpers will return `None` and functions
should gracefully fall back to in-memory behavior.
"""
from __future__ import annotations

import os
import json
from typing import Any, Optional

try:
    import redis.asyncio as aioredis
except Exception:  # pragma: no cover - optional dependency
    aioredis = None  # type: ignore

_redis_client: Optional["aioredis.Redis"] = None


def get_redis() -> Optional["aioredis.Redis"]:
    """Return a singleton Redis client or None if redis not configured.

    Callers should tolerate a `None` return and fall back to local cache.
    """
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    url = os.environ.get("REDIS_URL")
    if not url or aioredis is None:
        return None

    _redis_client = aioredis.from_url(url, decode_responses=True)
    return _redis_client


async def redis_get(key: str) -> Optional[str]:
    client = get_redis()
    if client is None:
        return None
    try:
        return await client.get(key)
    except Exception:
        return None


async def redis_set(key: str, value: str, ex: Optional[int] = None) -> bool:
    client = get_redis()
    if client is None:
        return False
    try:
        await client.set(key, value, ex=ex)
        return True
    except Exception:
        return False


async def redis_set_json(key: str, obj: Any, ex: Optional[int] = None) -> bool:
    return await redis_set(key, json.dumps(obj), ex=ex)


async def redis_get_json(key: str) -> Optional[Any]:
    s = await redis_get(key)
    if s is None:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None
