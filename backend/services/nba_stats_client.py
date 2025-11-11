"""Lightweight wrapper around `nba_api` with caching and safe fallbacks.

Provides:
- `find_player_id_by_name(name)` -> int | None
- `fetch_recent_games(player_id, limit=8)` -> list[dict]

If `nba_api` is missing, functions return `None` or empty lists and callers
should handle those cases. Redis caching is used when available via
`backend.services.cache` helpers.
"""
from __future__ import annotations

import os
import time
import json
import logging
from typing import Optional, List

from cachetools import TTLCache

from backend.services.cache import get_redis, redis_get_json, redis_set_json
import time
import threading

# Simple rate limiter: allow up to `MAX_REQUESTS_PER_MINUTE` calls to nba_api
# across this process. Implemented with a thread-safe token bucket.
MAX_REQUESTS_PER_MINUTE = int(os.environ.get('NBA_API_MAX_RPM', '20'))
_tokens = MAX_REQUESTS_PER_MINUTE
_last_refill = time.time()
_lock = threading.Lock()


def _acquire_token():
    global _tokens, _last_refill
    with _lock:
        now = time.time()
        elapsed = now - _last_refill
        # refill tokens
        if elapsed > 0:
            refill = elapsed * (MAX_REQUESTS_PER_MINUTE / 60.0)
            _tokens = min(MAX_REQUESTS_PER_MINUTE, _tokens + refill)
            _last_refill = now
        if _tokens >= 1:
            _tokens -= 1
            return True
        return False


def _wait_for_token(timeout: float = 10.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if _acquire_token():
            return True
        time.sleep(0.1)
    return False


def _with_retries(fn, *args, retries=3, backoff=0.5, **kwargs):
    """Helper to call `fn` with retries and exponential backoff."""
    last_exc = None
    for i in range(retries):
        # respect rate limit
        ok = _wait_for_token(timeout=5.0)
        if not ok:
            # failed to acquire token in time
            time.sleep(backoff * (i + 1))
            continue
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_exc = e
            time.sleep(backoff * (2 ** i))
            continue
    # final attempt without rate-limit block
    try:
        return fn(*args, **kwargs)
    except Exception:
        if last_exc:
            raise last_exc
        raise

logger = logging.getLogger(__name__)

# Try importing nba_api; it's optional for local dev
try:
    from nba_api.stats.static import players
    from nba_api.stats.endpoints import playergamelog
    from nba_api.stats.endpoints import playercareerstats
except Exception:  # pragma: no cover - optional dep
    players = None
    playergamelog = None
    playercareerstats = None

# in-memory TTL cache as fallback
_local_cache = TTLCache(maxsize=1000, ttl=60 * 10)


def _redis_client():
    return get_redis()


def find_player_id_by_name(name: str) -> Optional[int]:
    """Resolve a player name to the NBA player id using `nba_api`.

    Returns `None` if not found or `nba_api` not installed.
    """
    if not name:
        return None

    cache_key = f"player_id:{name}"
    # Try redis
    try:
        rc = _redis_client()
        if rc:
            cached = rc.get(cache_key)
            if cached:
                return int(cached)
    except Exception:
        pass

    # In-memory
    if cache_key in _local_cache:
        return _local_cache[cache_key]

    if players is None:
        return None

    try:
        # use retries + rate limiting
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
        pass

    # fallback: scan all players with simple normalization
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

    If `nba_api` is missing returns an empty list.
    """
    if not player_id:
        return []

    cache_key = f"player_recent:{player_id}:{limit}"
    try:
        cached = redis_get_json(cache_key) if _redis_client() else None
        if cached:
            return cached  # type: ignore
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
    except Exception as e:
        logger.exception("Error fetching recent games: %s", e)
        return []
"""Simple NBA stats client wrapper.

This is a thin wrapper around the existing `fastapi_nba.py` logic and/or
`nba_api` usage. It exposes helper functions used by other backend services.
"""
from typing import Optional, List, Dict
import os
import logging

logger = logging.getLogger(__name__)

try:
    # prefer using nba_api when available
    from nba_api.stats.static import players
    from nba_api.stats.endpoints import playergamelog
except Exception:
    players = None
    playergamelog = None


def find_player_id(name: str) -> Optional[int]:
    """Return player id or None if not found."""
    if players is None:
        logger.debug("nba_api not installed; cannot resolve player id")
        return None
    try:
        matches = players.find_players_by_full_name(name)
        if matches:
            return matches[0].get("id")
    except Exception:
        pass
    return None


def fetch_recent_games_by_id(player_id: int, limit: int = 8) -> List[Dict]:
    """Fetch recent games for a player ID. Returns list of raw rows (dicts).

    Falls back to empty list if `nba_api` not available.
    """
    if playergamelog is None:
        logger.debug("playergamelog not available; returning empty recent games")
        return []

    try:
        gl = playergamelog.PlayerGameLog(player_id=player_id)
        df = gl.get_data_frames()[0]
        return df.head(limit).to_dict(orient="records")
    except Exception as e:
        logger.exception("error fetching game log: %s", e)
        return []


def fetch_recent_games_by_name(name: str, limit: int = 8) -> List[Dict]:
    pid = find_player_id(name)
    if not pid:
        return []
    return fetch_recent_games_by_id(pid, limit=limit)
