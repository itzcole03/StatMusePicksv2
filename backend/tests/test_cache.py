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
