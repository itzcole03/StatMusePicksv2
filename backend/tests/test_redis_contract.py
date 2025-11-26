import importlib


def test_cache_helpers_exist():
    from backend.services import cache

    assert hasattr(cache, "get_sync_redis")
    assert hasattr(cache, "get_async_redis")


def test_nba_client_uses_sync_getter(monkeypatch):
    # Import the nba client module and replace its local get_sync_redis
    from backend.services import nba_stats_client as nbc

    sentinel = object()

    # Replace the module-level reference to get_sync_redis with a lambda
    monkeypatch.setattr(nbc, "get_sync_redis", lambda: sentinel)

    # _redis_client() should call the monkeypatched getter and return sentinel
    rc = nbc._redis_client()
    assert rc is sentinel
