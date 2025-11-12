import asyncio

import pytest
import asyncio

from backend.services import cache


def test_redis_fallback_set_get_delete():
    key = "test:cache:key"
    value = {"a": 1, "b": "x"}

    async def run_test():
        # ensure clean
        await cache.redis_delete(key)

        ok = await cache.redis_set_json(key, value, ex=2)
        assert ok is True

        got = await cache.redis_get_json(key)
        assert got == value

        deleted = await cache.redis_delete(key)
        assert deleted is True

        missing = await cache.redis_get_json(key)
        assert missing is None

    asyncio.run(run_test())


def test_redis_fallback_ttl_and_prefix_delete():
    """Validate TTL expiry and prefix-based invalidation on the fallback store."""
    key = "ttl:test:key"
    value = {"x": 42}

    async def run_ttl_test():
        # ensure clean
        await cache.redis_delete(key)

        ok = await cache.redis_set_json(key, value, ex=1)
        assert ok is True

        got = await cache.redis_get_json(key)
        assert got == value

        # wait for expiry
        await asyncio.sleep(1.2)
        expired = await cache.redis_get_json(key)
        assert expired is None

        # Test prefix delete
        await cache.redis_set_json("pref:a:1", {"v": 1})
        await cache.redis_set_json("pref:a:2", {"v": 2})
        await cache.redis_set_json("pref:b:1", {"v": 3})

        deleted = await cache.redis_delete_prefix("pref:a:")
        # On fallback this should delete two keys
        assert deleted >= 2

        remaining = await cache.redis_get_json("pref:b:1")
        assert remaining == {"v": 3}

    asyncio.run(run_ttl_test())


def test_cache_metrics():
    """Ensure basic metrics (sets/hits/misses) are tracked by the fallback."""
    key = "metrics:test:key"
    val = {"n": 5}

    async def run_metrics():
        # reset metrics first
        try:
            cache.reset_cache_metrics()
        except Exception:
            pass

        await cache.redis_delete(key)
        assert cache.get_cache_metrics() is not None

        await cache.redis_set_json(key, val, ex=2)
        # hit
        got = await cache.redis_get_json(key)
        assert got == val
        # miss
        await cache.redis_delete(key)
        missing = await cache.redis_get_json(key)
        assert missing is None

        metrics = cache.get_cache_metrics()
        assert metrics["sets"] >= 1
        # we expect at least one hit and one miss observed
        assert metrics["hits"] >= 1
        assert metrics["misses"] >= 1

    asyncio.run(run_metrics())
