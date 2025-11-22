"""LLM-based qualitative feature extraction service.

This is a lightweight scaffold that fetches text (news/summaries) and
extracts simple numeric signals that can be included as model features.
It uses a pluggable LLM client (not included) and a Redis cache + in-process
fallback to keep calls idempotent and cheap.
"""
from __future__ import annotations
import hashlib
import json
import logging
import os
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Keep a tiny in-process fallback cache for dev when Redis is unavailable
_fallback_cache: Dict[str, Dict] = {}


class LLMFeatureService:
    def __init__(self, redis_client: Optional[object] = None, ttl_seconds: int = 24 * 3600):
        self.redis = redis_client
        self.ttl = int(ttl_seconds)

    def _cache_key(self, player_name: str, source_id: str) -> str:
        key_raw = f"llm_feat:{player_name}:{source_id}"
        return hashlib.sha1(key_raw.encode("utf-8")).hexdigest()

    def _get_cached(self, key: str) -> Optional[Dict]:
        if self.redis:
            try:
                v = self.redis.get(key)
                if v:
                    return json.loads(v)
            except Exception:
                logger.exception("Redis read failed for %s", key)
        return _fallback_cache.get(key)

    def _set_cached(self, key: str, value: Dict) -> None:
        if self.redis:
            try:
                self.redis.set(key, json.dumps(value), ex=self.ttl)
                return
            except Exception:
                logger.exception("Redis write failed for %s", key)
        _fallback_cache[key] = value

    def extract_features_from_text(self, player_name: str, text: str) -> Dict[str, float]:
        """Extract numeric features from arbitrary text via an LLM or heuristics.

        For now this is a safe fallback implementation using simple heuristics:
        - `injury_sentiment`: -1..1 where negative indicates injury-related mentions
        - `morale_score`: -1..1 sentiment proxy
        - `motivation`: 0..1 indicator for contract-year/award mentions
        """
        # simple hash-based deterministic placeholder so outputs are stable in dev
        h = int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:8], 16)
        injury = ((h % 200) - 100) / 100.0
        morale = ((h >> 3) % 200 - 100) / 100.0
        motivation = ((h >> 6) % 100) / 100.0
        return {
            "injury_sentiment": float(max(-1.0, min(1.0, injury))),
            "morale_score": float(max(-1.0, min(1.0, morale))),
            "motivation": float(max(0.0, min(1.0, motivation))),
        }

    def fetch_news_and_extract(self, player_name: str, source_id: str, text_fetcher) -> Dict[str, float]:
        """Fetch textual context via `text_fetcher(player_name)` and extract features.

        `source_id` is a small string used to version/cache the extraction (eg. 'news_v1').
        `text_fetcher` must be a callable that returns a string (or raises).
        """
        key = self._cache_key(player_name, source_id)
        cached = self._get_cached(key)
        if cached:
            return cached

        try:
            text = text_fetcher(player_name)
        except Exception:
            logger.exception("text_fetcher failed for %s", player_name)
            # return neutral features on failure
            result = {"injury_sentiment": 0.0, "morale_score": 0.0, "motivation": 0.0}
            self._set_cached(key, result)
            return result

        result = self.extract_features_from_text(player_name, text or "")
        # persist
        try:
            self._set_cached(key, result)
        except Exception:
            logger.exception("Failed to cache llm features for %s", player_name)
        return result


# Helper factory for default usage; in the real app pass a Redis client
def create_default_service():
    redis_url = os.environ.get("REDIS_URL")
    redis_client = None
    if redis_url:
        try:
            import redis as _redis

            redis_client = _redis.from_url(redis_url)
        except Exception:
            logger.exception("Failed to create redis client from REDIS_URL")
    return LLMFeatureService(redis_client=redis_client)
