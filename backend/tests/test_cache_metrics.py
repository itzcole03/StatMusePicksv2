import asyncio

import pytest

from backend.services import cache as cache_mod


@pytest.mark.asyncio
async def test_fallback_set_get_delete_metrics():
    # Ensure fresh metrics
    cache_mod.reset_cache_metrics()

    key = "test:metric:key"
    # ensure key not present
    val = await cache_mod.redis_get_json(key)
    assert val is None

    # set value using fallback (no Redis configured in test env)
    ok = await cache_mod.redis_set_json(key, {"x": 1}, ex=2)
    assert ok is True

    metrics = cache_mod.get_cache_metrics()
    assert metrics.get("sets", 0) >= 1

    # get should hit
    got = await cache_mod.redis_get_json(key)
    assert got == {"x": 1}
    metrics = cache_mod.get_cache_metrics()
    assert metrics.get("hits", 0) >= 1

    # delete the key
    existed = await cache_mod.redis_delete(key)
    assert existed is True
    metrics = cache_mod.get_cache_metrics()
    assert metrics.get("deletes", 0) >= 1


@pytest.mark.asyncio
async def test_fallback_expiry():
    cache_mod.reset_cache_metrics()
    key = "test:expiry:key"
    await cache_mod.redis_set_json(key, {"y": 2}, ex=1)
    v1 = await cache_mod.redis_get_json(key)
    assert v1 == {"y": 2}
    # wait for expiry
    await asyncio.sleep(1.2)
    v2 = await cache_mod.redis_get_json(key)
    assert v2 is None
