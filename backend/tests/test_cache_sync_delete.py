import asyncio
import os

import pytest

from backend.services import cache


def setup_module(module):
    # ensure we run against the in-process fallback for determinism
    # Monkeypatching environment is done per-test; ensure REDIS_URL not set here
    os.environ.pop("REDIS_URL", None)


def test_redis_delete_prefix_sync_no_loop(monkeypatch):
    # Ensure get_redis returns None to use fallback store
    monkeypatch.setattr(cache, "get_redis", lambda: None)
    # Ensure `import redis` fails so sync redis client path is not used
    import builtins
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "redis":
            raise ImportError("simulated missing redis")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    # Populate fallback store via async setter
    asyncio.run(cache.redis_set_json("player_context:Test Player:1", {"v": 1}))
    asyncio.run(cache.redis_set_json("player_context:Other Player:2", {"v": 2}))

    assert "player_context:Test Player:1" in cache._fallback_store
    assert "player_context:Other Player:2" in cache._fallback_store

    deleted = cache.redis_delete_prefix_sync("player_context:Test Player:")
    assert deleted == 1
    assert "player_context:Test Player:1" not in cache._fallback_store
    assert "player_context:Other Player:2" in cache._fallback_store


def test_redis_delete_prefix_sync_with_loop_running(monkeypatch):
    # Force fallback path and simulate loop running/failure of run_coroutine_threadsafe
    monkeypatch.setattr(cache, "get_redis", lambda: None)
    # Ensure `import redis` fails so sync redis client path is not used
    import builtins
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "redis":
            raise ImportError("simulated missing redis")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    # Put two keys
    asyncio.run(cache.redis_set_json("predict:Player A:line", {"v": 1}))
    asyncio.run(cache.redis_set_json("predict:Player B:line", {"v": 2}))

    assert "predict:Player A:line" in cache._fallback_store
    assert "predict:Player B:line" in cache._fallback_store

    # Simulate an event loop that is running by monkeypatching asyncio.get_event_loop
    class FakeLoop:
        def is_running(self):
            return True

    monkeypatch.setattr(asyncio, "get_event_loop", lambda: FakeLoop())

    # Force run_coroutine_threadsafe to raise so code falls back to iterative deletion
    def _raise(*args, **kwargs):
        raise RuntimeError("simulated run_coroutine_threadsafe failure")

    monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", _raise)

    deleted = cache.redis_delete_prefix_sync("predict:Player A:")
    # Deletion should have removed the A key
    assert deleted >= 1
    assert "predict:Player A:line" not in cache._fallback_store
    assert "predict:Player B:line" in cache._fallback_store
