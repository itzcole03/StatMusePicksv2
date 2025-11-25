import os
import pytest

from backend.services.llm_feature_service import LLMFeatureService


# This smoke test exercises a live Ollama/cloud instance. It is skipped
# unless an Ollama API key is provided via the environment. DO NOT commit
# API keys into source control — set `OLLAMA_CLOUD_API_KEY` or
# `OLLAMA_API_KEY` in your CI or local environment instead.
OLLAMA_KEY = os.environ.get('OLLAMA_CLOUD_API_KEY') or os.environ.get('OLLAMA_API_KEY')

pytestmark = pytest.mark.skipif(not OLLAMA_KEY, reason="OLLAMA API key not set; live smoke test skipped")


def test_ollama_smoke_runs_and_returns_structured_features():
    """Live smoke test: call the LLM extraction pipeline and check keys.

    This test intentionally makes a short, bounded call to the real LLM
    service. It asserts only that a structured dict with the expected
    qualitative feature keys is returned. Keep the test minimal so it can
    be used as a CI smoke when a secure key is available.
    """
    svc = LLMFeatureService()
    # Use a small number of attempts to bound test runtime
    out = svc.extract_from_text(
        "Smoke Player",
        "Recent report: Player suffered a minor ankle sprain and is listed as questionable.",
        max_attempts=2,
    )

    assert isinstance(out, dict)
    # ensure expected schema keys present (values may vary by model)
    for key in ("injury_status", "morale_score", "news_sentiment", "trade_sentiment", "motivation"):
        assert key in out
