"""Synchronous NBA stats client helpers used by backend code.

This module provides two helpers expected by `fastapi_nba.py` and other
backend modules: `find_player_id_by_name(name)` and `fetch_recent_games(player_id, limit)`.

Behavior:
- Prefer Redis caching via `backend.services.cache.get_redis()` when available.
- Fall back to an in-process TTL cache for local dev/tests.
- Use `nba_api` when installed; otherwise functions return `None` or []
  so callers can handle missing data gracefully.
"""
from __future__ import annotations

import json
import logging
import os
import time
import threading
from typing import Optional, List, Dict

from cachetools import TTLCache

from backend.services.cache import get_redis

logger = logging.getLogger(__name__)

# Try importing nba_api optional dependency
try:
    from nba_api.stats.static import players
    from nba_api.stats.endpoints import playergamelog
    from nba_api.stats.endpoints import playercareerstats
except Exception:  # pragma: no cover - optional dep
    players = None
    playergamelog = None
    playercareerstats = None


# In-process TTL cache as a fallback when Redis is unavailable
_local_cache = TTLCache(maxsize=2000, ttl=60 * 10)

# Simple token-bucket style rate limiter shared across sync calls
MAX_REQUESTS_PER_MINUTE = int(os.environ.get("NBA_API_MAX_RPM", "20"))
_tokens = float(MAX_REQUESTS_PER_MINUTE)
_last_refill = time.time()
_rl_lock = threading.Lock()


def _acquire_token(timeout: float = 5.0) -> bool:
    """Attempt to acquire a token within `timeout` seconds."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with _rl_lock:
            global _tokens, _last_refill
            now = time.time()
            elapsed = now - _last_refill
            if elapsed > 0:
                refill = elapsed * (MAX_REQUESTS_PER_MINUTE / 60.0)
                _tokens = min(float(MAX_REQUESTS_PER_MINUTE), _tokens + refill)
                _last_refill = now
            if _tokens >= 1.0:
                _tokens -= 1.0
                return True
        time.sleep(0.05)
    return False


def _with_retries(fn, *args, retries: int = 3, backoff: float = 0.5, **kwargs):
    last_exc = None
    for attempt in range(retries):
        ok = _acquire_token(timeout=2.0)
        if not ok:
            time.sleep(backoff * (attempt + 1))
            continue
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_exc = e
            time.sleep(backoff * (2 ** attempt))
    # final attempt without waiting for token
    try:
        return fn(*args, **kwargs)
    except Exception:
        if last_exc:
            raise last_exc
        raise


def _redis_client():
    return get_redis()


def find_player_id_by_name(name: str) -> Optional[int]:
    """Resolve a player name to the NBA player id.

    Tries Redis -> in-process TTLCache -> `nba_api` calls (with retries/rate-limit).
    Returns `None` if not resolvable.
    """
    if not name:
        return None

    cache_key = f"player_id:{name}"

    # Redis cache
    try:
        rc = _redis_client()
        if rc:
            raw = rc.get(cache_key)
            if raw:
                try:
                    return int(raw)
                except Exception:
                    try:
                        return int(raw.decode("utf-8"))
                    except Exception:
                        return None
    except Exception:
        pass

    # in-memory cache
    if cache_key in _local_cache:
        return _local_cache[cache_key]

    if players is None:
        return None

    try:
        def _lookup(n):
            return players.find_players_by_full_name(n)

        matches = _with_retries(_lookup, name)
        if matches:
            pid = matches[0]["id"]
            _local_cache[cache_key] = pid
            try:
                rc = _redis_client()
                if rc:
                    rc.setex(cache_key, 60 * 60 * 24, str(pid))
            except Exception:
                pass
            return pid
    except Exception:
        logger.debug("player id lookup failed for %s", name, exc_info=True)

    # fallback: scan all players for a best-effort match
    def normalize(n: str) -> str:
        import re

        n = (n or "").lower()
        n = re.sub(r"[,\.]", "", n)
        n = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", n)
        n = re.sub(r"\s+", " ", n).strip()
        return n

    try:
        allp = players.get_players()
    except Exception:
        return None

    target = normalize(name)
    for p in allp:
        if normalize(p.get("full_name", "")) == target:
            pid = p["id"]
            _local_cache[cache_key] = pid
            return pid

    for p in allp:
        if target in normalize(p.get("full_name", "")):
            pid = p["id"]
            _local_cache[cache_key] = pid
            return pid

    return None


def fetch_recent_games(player_id: int, limit: int = 8) -> List[dict]:
    """Fetch recent game logs for a player id. Returns list of raw game dicts.

    Tries Redis -> in-process TTLCache -> `nba_api` PlayerGameLog.
    Returns empty list when data isn't available.
    """
    if not player_id:
        return []

    cache_key = f"player_recent:{player_id}:{limit}"

    try:
        rc = _redis_client()
        if rc:
            raw = rc.get(cache_key)
            if raw:
                try:
                    return json.loads(raw) if not isinstance(raw, (bytes, bytearray)) else json.loads(raw.decode("utf-8"))
                except Exception:
                    pass
    except Exception:
        pass

    if cache_key in _local_cache:
        return _local_cache[cache_key]

    if playergamelog is None:
        return []

    try:
        def _fetch(pid, lim):
            gl = playergamelog.PlayerGameLog(player_id=pid)
            df = gl.get_data_frames()[0]
            return df.head(lim).to_dict(orient="records")

        recent = _with_retries(_fetch, player_id, limit)
        _local_cache[cache_key] = recent
        try:
            rc = _redis_client()
            if rc:
                rc.setex(cache_key, 60 * 10, json.dumps(recent))
        except Exception:
            pass
        return recent
    except Exception:
        logger.exception("Error fetching recent games for player_id=%s", player_id)
        return []


__all__ = ["find_player_id_by_name", "fetch_recent_games"]
