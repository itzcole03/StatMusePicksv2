import pytest
import requests

from backend.services import nba_stats_client as nbc


def test_with_retries_succeeds_after_transient(monkeypatch):
    calls = {"count": 0}

    def flaky(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise requests.exceptions.ConnectionError("transient")
        return "ok"

    monkeypatch.setattr(nbc, "_acquire_token", lambda timeout=2.0: True)
    res = nbc._with_retries(flaky, retries=5, backoff=0.001)
    assert res == "ok"
    assert calls["count"] == 3


def test_with_retries_raises_last_exception(monkeypatch):
    calls = {"count": 0}

    def always_fail(*args, **kwargs):
        calls["count"] += 1
        raise ValueError("persistent")

    monkeypatch.setattr(nbc, "_acquire_token", lambda timeout=2.0: True)
    with pytest.raises(ValueError):
        nbc._with_retries(always_fail, retries=3, backoff=0.001)
    assert calls["count"] >= 1


def test_with_retries_respects_token_acquire(monkeypatch):
    # Simulate _acquire_token returning False twice, then True.
    state = {"acquires": 0}

    def acquire(timeout=2.0):
        state["acquires"] += 1
        return state["acquires"] >= 3

    monkeypatch.setattr(nbc, "_acquire_token", acquire)

    def fast_ok(*args, **kwargs):
        return "ok"

    res = nbc._with_retries(fast_ok, retries=5, backoff=0.001)
    assert res == "ok"
    assert state["acquires"] >= 3
