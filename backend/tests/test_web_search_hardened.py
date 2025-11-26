import os
import time

from backend.services import web_search


def test_sanitize_and_stub():
    # No BING key set in CI; expect stub or ddg fallback but not crash
    os.environ.pop("BING_API_KEY", None)
    res = web_search.web_search("  LeBron James injury update \n\x00\x01")
    assert isinstance(res, str)
    # sanitized query should not include control chars
    assert "\x00" not in res


def test_rate_limit():
    # set low rate for test
    os.environ["WEB_SEARCH_MAX_RPM"] = "2"
    # reset internal bucket
    web_search._ws_bucket["tokens"] = float(2)
    web_search._ws_bucket["last"] = time.time()

    web_search.web_search("one")
    web_search.web_search("two")
    out3 = web_search.web_search("three")

    # third call should be rate limited (either stub or explicit marker)
    assert isinstance(out3, str)
    assert out3.startswith("[") or "rate" in out3.lower()
