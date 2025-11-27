from backend.services import web_search


class FakeRedis:
    def __init__(self, responses):
        # responses is iterator or list of returns for eval
        self._responses = list(responses)

    def eval(self, script, numkeys, key, now, rate, amount):
        if not self._responses:
            return 0
        return self._responses.pop(0)


def test_web_search_uses_redis_bucket(monkeypatch):
    fake = FakeRedis([1, 0])

    # monkeypatch get_sync_redis in cache module used by web_search
    import backend.services.cache as cache

    monkeypatch.setattr(cache, "get_sync_redis", lambda: fake)

    # first call allowed
    out1 = web_search.web_search("first")
    assert isinstance(out1, str)

    # second call should be rate-limited by fake.eval returning 0
    out2 = web_search.web_search("second")
    assert isinstance(out2, str)
    assert "rate" in out2.lower() or out2.startswith("[")
