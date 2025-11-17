import os
import time
import json

import redis
from fastapi.testclient import TestClient

from backend import fastapi_nba


# Integration test: requires a real Redis server reachable at REDIS_HOST:REDIS_PORT
# This test is intended to run in CI where a Redis service is provided.

REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))


def test_predict_sets_redis_key_and_ttl(monkeypatch):
    # Use a real Redis client and point the app's redis_client at it
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)

    # make sure redis is reachable; skip test early if not
    try:
        r.ping()
    except Exception as e:
        raise RuntimeError(f"Redis not reachable at {REDIS_HOST}:{REDIS_PORT}: {e}")

    # patch the module-level redis_client to use the real redis
    monkeypatch.setattr(fastapi_nba, 'redis_client', r)

    client = TestClient(fastapi_nba.app)

    payload = {
        'player': 'Integration_Player',
        'stat': 'points',
        'line': 15.0,
        'player_data': { 'rollingAverages': {'last5Games': 16.0}, 'seasonAvg': 16.0 },
        'opponent_data': {}
    }

    # call predict; this should set the redis key via `setex`
    rv = client.post('/api/predict', json=payload)
    assert rv.status_code == 200
    body = rv.json()
    # compute the cache key used in fastapi_nba
    cache_key = f"predict:{payload['player']}:{payload['stat']}:{payload['line']}"

    # Give Redis a tiny moment to persist
    time.sleep(0.1)

    raw = r.get(cache_key)
    assert raw is not None, "expected cache key to be set in redis"

    # TTL should be approx 3600 seconds (1 hour). Accept a small delta.
    ttl = r.ttl(cache_key)
    assert ttl is not None and ttl > 3500 and ttl <= 3600

    # Cleanup
    r.delete(cache_key)
