"""Advanced NBA metrics fetcher scaffold.

Provides functions to compute or fetch advanced metrics (PER, TS%, USG%, ORtg/DRtg)
for players/teams. Uses existing `backend/services/nba_stats_client.py` when available.
Caching via Redis or in-process fallback is supported.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_fallback_cache: Dict[str, Dict] = {}


class AdvancedMetricsService:
    def __init__(
        self, redis_client: Optional[object] = None, ttl_seconds: int = 6 * 3600
    ):
        self.redis = redis_client
        self.ttl = int(ttl_seconds)

    def _cache_key(self, player_id: str) -> str:
        return f"adv_metrics:{player_id}"

    def _get_cached(self, key: str) -> Optional[Dict]:
        if self.redis:
            try:
                v = self.redis.get(key)
                if v:
                    import json

                    return json.loads(v)
            except Exception:
                logger.exception("Redis read failed for %s", key)
        return _fallback_cache.get(key)

    def _set_cached(self, key: str, value: Dict) -> None:
        if self.redis:
            try:
                import json

                self.redis.set(key, json.dumps(value), ex=self.ttl)
                return
            except Exception:
                logger.exception("Redis write failed for %s", key)
        _fallback_cache[key] = value

    def fetch_advanced_metrics(self, player_id: str) -> Optional[Dict]:
        """Fetch advanced metrics for `player_id`.

        Attempts to use `backend.services.nba_stats_client` if available; otherwise
        returns None. Results are cached.
        """
        key = self._cache_key(player_id)
        cached = self._get_cached(key)
        if cached:
            return cached
        try:
            # Import the functional helpers (module may not expose a class wrapper)
            # Use importlib.import_module so test monkeypatching of
            # `backend.services.nba_stats_client` in `sys.modules` is respected.
            import importlib

            nba = importlib.import_module("backend.services.nba_stats_client")

            # Determine season to query: prefer env override, otherwise derive a recent season
            season = os.environ.get("NBA_DEFAULT_SEASON")
            if not season:
                try:
                    import datetime

                    now = datetime.datetime.now(datetime.timezone.utc)
                    y = now.year
                    # crude season string like '2024-25' for Nov/Dec belong to prior-year start
                    if now.month < 8:
                        season = f"{y-1}-{str(y)[-2:]}"
                    else:
                        season = f"{y}-{str(y+1)[-2:]}"
                except Exception:
                    season = "2024-25"

            # Try the most specific API first, then fall back
            metrics = None
            try:
                # many helpers expect numeric ids
                pid_int = int(player_id)
            except Exception:
                pid_int = None

            # Support alternative client interface used in tests: NBAStatsClient
            try:
                if hasattr(nba, "NBAStatsClient"):
                    try:
                        client = nba.NBAStatsClient()
                        # Try numeric id first, then fallback to original string id
                        client_arg = pid_int if pid_int is not None else player_id
                        if hasattr(client, "fetch_advanced_player_metrics"):
                            metrics = client.fetch_advanced_player_metrics(client_arg)
                        elif hasattr(client, "get_advanced_player_stats"):
                            metrics = client.get_advanced_player_stats(client_arg)
                    except Exception:
                        metrics = None
            except Exception:
                pass

            if pid_int is not None:
                try:
                    metrics = nba.get_advanced_player_stats(pid_int, season)
                except Exception:
                    metrics = None

                if not metrics:
                    try:
                        metrics = nba.get_advanced_player_stats_fallback(
                            pid_int, season
                        )
                    except Exception:
                        metrics = None

            if not metrics:
                return None

            # normalize keys we care about (mapping tolerated across helper variants)
            result = {
                "PER": metrics.get("PER") or metrics.get("per") or metrics.get("Per"),
                "TS_pct": metrics.get("TS_PCT")
                or metrics.get("TS_PCT")
                or metrics.get("TS_pct")
                or metrics.get("TS"),
                "USG_pct": metrics.get("USG_PCT")
                or metrics.get("USG_pct")
                or metrics.get("USG"),
                "ORtg": metrics.get("OFF_RATING")
                or metrics.get("ORtg")
                or metrics.get("off_rating"),
                "DRtg": metrics.get("DEF_RATING")
                or metrics.get("DRtg")
                or metrics.get("def_rating"),
            }

            # Try to extract Box Plus/Minus (BPM) if present in various possible keys.
            bpm = (
                metrics.get("BPM")
                or metrics.get("BPM_RATING")
                or metrics.get("BPM_48")
                or metrics.get("BPM48")
                or metrics.get("BOX_PLUS_MINUS")
                or metrics.get("box_plus_minus")
            )
            # Try to extract Win Shares (season total) when available
            ws = (
                metrics.get("WS")
                or metrics.get("WinShares")
                or metrics.get("win_shares")
                or metrics.get("Win_Shares")
            )
            try:
                if ws is not None:
                    result["WS"] = float(ws)
                else:
                    result["WS"] = None
            except Exception:
                result["WS"] = None
            try:
                if bpm is not None:
                    result["BPM"] = float(bpm)
                else:
                    # Provide a conservative approximation when BPM isn't available.
                    # BPM is roughly correlated with PER; use (PER - 15) scaled as a proxy.
                    per_val = result.get("PER")
                    if per_val is not None:
                        try:
                            result["BPM_approx"] = float((float(per_val) - 15.0) * 0.4)
                        except Exception:
                            result["BPM_approx"] = None
                    else:
                        result["BPM_approx"] = None
            except Exception:
                result["BPM"] = None
                result["BPM_approx"] = None

            try:
                self._set_cached(key, result)
            except Exception:
                logger.exception("Failed to cache advanced metrics for %s", player_id)
            return result
        except Exception:
            logger.exception("Failed to fetch advanced metrics for %s", player_id)
            return None


def create_default_service():
    redis_url = os.environ.get("REDIS_URL")
    redis_client = None
    if redis_url:
        try:
            import redis as _redis

            redis_client = _redis.from_url(redis_url)
        except Exception:
            logger.exception("Failed to create redis client from REDIS_URL")
    return AdvancedMetricsService(redis_client=redis_client)
