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
import logging
from typing import Any, Optional

try:
    import redis.asyncio as aioredis  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    aioredis = None  # type: ignore

try:
    from prometheus_client import Counter  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Counter = None  # type: ignore

_redis_client: Optional["aioredis.Redis"] = None
_fallback_store: dict[str, dict] = {}
_fallback_lock = asyncio.Lock()
_metrics = {
    "hits": 0,
    "misses": 0,
    "sets": 0,
    "deletes": 0,
}

# module logger
_logger = logging.getLogger(__name__)


def _inc_metric(name: str, amount: int = 1) -> None:
    if name in _metrics:
        _metrics[name] += amount
    # also increment prometheus counters if available
    try:
        if Counter is not None:
            # lazily create counters on first use
            global _prom_counters
            if '_prom_counters' not in globals():
                _prom_counters = {
                    'hits': Counter('cache_hits_total', 'Cache hits'),
                    'misses': Counter('cache_misses_total', 'Cache misses'),
                    'sets': Counter('cache_sets_total', 'Cache sets'),
                    'deletes': Counter('cache_deletes_total', 'Cache deletes'),
                }
            cnt = globals()['_prom_counters'].get(name)
            if cnt is not None:
                cnt.inc(amount)
    except Exception:
        # do not fail if prometheus instrumentation has issues
        pass


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
        _inc_metric("sets")
        return True

    try:
        await client.set(key, json.dumps(obj), ex=ex)
        return True
    except Exception:
        return False


async def redis_get_json(key: str) -> Optional[Any]:
    """Retrieve JSON object stored at `key`, or None if missing/expired.

    Prefer a real Redis client when available. When falling back to the
    in-memory store, consult both `_fallback_store` and the sync mirror
    `_fallback_store_sync` while holding `_fallback_lock` so synchronous
    deletions are visible to async readers.
    """
    client = get_redis()
    # Prefer real Redis when available
    if client is not None:
        try:
            raw = await client.get(key)
            if raw is None:
                _inc_metric("misses")
                return None
            _inc_metric("hits")
            return json.loads(raw)
        except Exception:
            # fall back to in-memory store
            _logger.exception("Error reading from redis, falling back to in-memory store")

    # Fallback path: check the single fallback store while holding the lock
    async with _fallback_lock:
        item = _fallback_store.get(key)
        if item is None:
            _inc_metric("misses")
            return None

        # item shape: {"v": json_str, "e": expiry_ts_or_None}
        expires = item.get("e")
        now = asyncio.get_event_loop().time()
        if expires is not None and now > expires:
            # remove expired entry
            try:
                if key in _fallback_store:
                    del _fallback_store[key]
            except Exception:
                pass
            _inc_metric("misses")
            return None

        try:
            val = json.loads(item["v"])
        except Exception:
            _inc_metric("misses")
            return None
        _inc_metric("hits")
        return val


async def redis_delete(key: str) -> bool:
    client = get_redis()
    if client is None:
        async with _fallback_lock:
            existed = key in _fallback_store
            if key in _fallback_store:
                del _fallback_store[key]
        return existed

    try:
        await client.delete(key)
        _inc_metric("deletes")
        return True
    except Exception:
        return False


async def _delete_prefix_async(prefix: str) -> int:
    """Async helper to delete keys with a prefix from the fallback store."""
    deleted = 0
    async with _fallback_lock:
        keys = [k for k in list(_fallback_store.keys()) if k.startswith(prefix)]
        for k in keys:
            try:
                del _fallback_store[k]
                deleted += 1
            except Exception:
                pass
    return deleted


async def redis_delete_prefix(prefix: str) -> int:
    """Delete keys that start with `prefix`. Returns number of keys deleted.

    Uses `SCAN` on real Redis for safety; falls back to scanning the in-memory store.
    """
    client = get_redis()
    deleted = 0
    if client is None:
        async with _fallback_lock:
            keys = [k for k in list(_fallback_store.keys()) if k.startswith(prefix)]
            for k in keys:
                del _fallback_store[k]
                deleted += 1
        _inc_metric("deletes")
        return deleted

    try:
        # Use scan_iter to avoid blocking Redis on large keyspaces
        async for k in client.scan_iter(match=prefix + "*"):
            await client.delete(k)
            deleted += 1
        _inc_metric("deletes", deleted)
        return deleted
    except Exception:
        return deleted


def redis_delete_prefix_sync(prefix: str) -> int:
    """Synchronous prefix delete helper for sync callers.

    Attempts to use the sync redis client if available, otherwise manipulates
    the in-memory fallback store. Returns number of keys deleted.
    """
    deleted = 0
    try:
        import redis as sync_redis
    except Exception:
        sync_redis = None

    # DEBUG: trace execution path
    try:
        import sys as _sys
        _sys.stdout.write(f"redis_delete_prefix_sync called prefix={prefix} sync_redis={'present' if sync_redis is not None else 'absent'}\n")
    except Exception:
        pass

    if sync_redis is None:
        # operate on fallback directly
        try:
            loop = asyncio.get_event_loop()
            running = loop.is_running()
        except RuntimeError:
            loop = None
            running = False

        if running:
            # can't run loop; best-effort: delete under the lock using run_coroutine_threadsafe
            coro = None
            try:
                coro = _delete_prefix_async(prefix)
                fut = asyncio.run_coroutine_threadsafe(coro, loop)
                deleted = fut.result()
            except Exception:
                # if scheduling failed, ensure coroutine is closed to avoid warnings
                try:
                    if coro is not None and asyncio.iscoroutine(coro):
                        coro.close()
                except Exception:
                    pass
                # fallback: iterate over keys (may race if loop is running)
                keys = [k for k in list(_fallback_store.keys()) if k.startswith(prefix)]
                for k in keys:
                    try:
                        del _fallback_store[k]
                        deleted += 1
                    except Exception:
                        pass
        else:
            # safe to run async cleanup synchronously
            async def _do():
                nonlocal deleted
                async with _fallback_lock:
                    keys = [k for k in list(_fallback_store.keys()) if k.startswith(prefix)]
                    for k in keys:
                        del _fallback_store[k]
                        deleted += 1

            asyncio.run(_do())
        _inc_metric("deletes", deleted)
        return deleted

    # use sync redis client
    url = os.environ.get("REDIS_URL") or "redis://127.0.0.1:6379/0"
    try:
        client = sync_redis.from_url(url, decode_responses=True)
        try:
            # If Redis server isn't responsive fall back to in-memory mirror
            try:
                _sys.stdout.write("redis client created, pinging...\n")
            except Exception:
                pass
            try:
                if not client.ping():
                    raise Exception("redis ping failed")
            except Exception as e:
                try:
                    _sys.stdout.write(f"redis ping failed: {e}\n")
                except Exception:
                    pass
                # fallback to deleting from the in-process fallback store
                keys = [k for k in list(_fallback_store.keys()) if k.startswith(prefix)]
                for k in keys:
                    try:
                        del _fallback_store[k]
                        deleted += 1
                    except Exception:
                        pass
                _inc_metric("deletes", deleted)
                return deleted

            for k in client.scan_iter(match=prefix + "*"):
                client.delete(k)
                deleted += 1
            _inc_metric("deletes", deleted)
            return deleted
        except Exception as e:
            try:
                _sys.stdout.write(f"redis scan/delete failed: {e}\n")
            except Exception:
                pass
            # Connection/scan failed; fall back to deleting from in-process store
            keys = [k for k in list(_fallback_store.keys()) if k.startswith(prefix)]
            for k in keys:
                try:
                    del _fallback_store[k]
                    deleted += 1
                except Exception:
                    pass
            _inc_metric("deletes", deleted)
            return deleted
    except Exception:
        # If creating client failed, also fall back to deleting from in-process store
        keys = [k for k in list(_fallback_store.keys()) if k.startswith(prefix)]
        for k in keys:
            try:
                del _fallback_store[k]
                deleted += 1
            except Exception:
                pass
        _inc_metric("deletes", deleted)
        return deleted


def get_cache_metrics() -> dict:
    """Return current cache metrics snapshot."""
    return dict(_metrics)


def reset_cache_metrics() -> None:
    for k in _metrics:
        _metrics[k] = 0


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
