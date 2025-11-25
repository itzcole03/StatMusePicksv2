import time
import threading

import pytest

from backend.services import nba_stats_client as ns


def _run_acquire(results, timeout=0.1):
    ok = ns._acquire_token(timeout=timeout)
    results.append(ok)


def test_token_bucket_concurrent_limit(monkeypatch):
    """Concurrent callers should only consume up to MAX_REQUESTS_PER_MINUTE tokens."""
    # Create a small token bucket and inject it
    tb = ns.TokenBucket(rpm=2)
    ns.set_token_bucket(tb)

    threads = []
    results = []
    # Start 6 concurrent threads trying to acquire tokens
    for _ in range(6):
        t = threading.Thread(target=_run_acquire, args=(results, 0.2))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Exactly 2 acquisitions should succeed (token bucket size)
    success_count = sum(1 for r in results if r)
    assert success_count == 2


def test_token_refills_over_time(monkeypatch):
    """After consuming tokens, waiting allows refill to permit new acquisitions."""
    # Use a refill rate of ~1 token/sec and simulate 2s of elapsed time
    tb = ns.TokenBucket(rpm=60)
    # force tokens to 0 and last_refill in the past so refill can occur
    tb._tokens = 0.0
    tb._last_refill = time.time() - 2.0
    ns.set_token_bucket(tb)

    # With a short timeout, acquire should eventually succeed due to refill
    ok = ns._acquire_token(timeout=1.0)
    assert ok is True
