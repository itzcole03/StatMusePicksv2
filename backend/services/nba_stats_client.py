"""Synchronous NBA stats client helpers used by backend code.

This module provides a compact, single-copy implementation of the
helpers used by `backend.fastapi_nba` and other services. It prefers
Redis for caching via `backend.services.cache.get_redis()` and falls
back to an in-process TTL cache. `nba_api` is optional and guarded so
the module works in environments without network access.
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
from backend.services.nba_normalize import canonicalize_rows

logger = logging.getLogger(__name__)

# Optional nba_api imports
try:
    from nba_api.stats.static import players
    from nba_api.stats.endpoints import playergamelog
    from nba_api.stats.endpoints import teamgamelog
    from nba_api.stats.endpoints import playercareerstats
except Exception:  # pragma: no cover - optional dep
    players = None
    playergamelog = None
    teamgamelog = None
    playercareerstats = None


# Local TTL cache used when Redis isn't configured
_local_cache = TTLCache(maxsize=2_000, ttl=60 * 10)

# Rate limiter (simple token bucket) for external calls
MAX_REQUESTS_PER_MINUTE = int(os.environ.get("NBA_API_MAX_RPM", "20"))
_tokens = float(MAX_REQUESTS_PER_MINUTE)
_last_refill = time.time()
_rl_lock = threading.Lock()


def _acquire_token(timeout: float = 5.0) -> bool:
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
    # final attempt
    try:
        return fn(*args, **kwargs)
    except Exception:
        if last_exc:
            raise last_exc
        raise


def _redis_client():
    return get_redis()


def find_player_id_by_name(name: str) -> Optional[int]:
    """Resolve a player full name to an NBA player id.

    Returns None when resolution is not possible in the current environment.
    """
    if not name:
        return None

    cache_key = f"player_id:{name}"
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
        # Redis may not be available in test/dev environments
        pass

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

    # best-effort scan
    try:
        allp = players.get_players()
    except Exception:
        return None

    def normalize(n: str) -> str:
        import re

        n = (n or "").lower()
        n = re.sub(r"[,\.]", "", n)
        n = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", n)
        n = re.sub(r"\s+", " ", n).strip()
        return n

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
    """Return recent game logs for a player id (list of dicts).

    If `nba_api` is unavailable the function returns an empty list.
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
        # Canonicalize and dedupe before caching/returning
        recent = canonicalize_rows(recent or [])
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


def find_player_id(name: str) -> Optional[int]:
    return find_player_id_by_name(name)


def fetch_recent_games_by_id(player_id: int, limit: int = 8) -> List[dict]:
    return fetch_recent_games(player_id, limit=limit)


def fetch_recent_games_by_name(name: str, limit: int = 8) -> List[dict]:
    pid = find_player_id_by_name(name)
    if pid:
        return fetch_recent_games_by_id(pid, limit=limit)
    return []


def fetch_games_by_season(player_id: int, season: str) -> List[dict]:
    if not player_id or not season:
        return []

    cache_key = f"player_games_season:{player_id}:{season}"
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
        def _fetch(pid, s):
            gl = playergamelog.PlayerGameLog(player_id=pid, season=s)
            df = gl.get_data_frames()[0]
            return df.to_dict(orient="records")

        rows = _with_retries(_fetch, player_id, season)
        rows = canonicalize_rows(rows or [])
        _local_cache[cache_key] = rows
        try:
            rc = _redis_client()
            if rc:
                rc.setex(cache_key, 60 * 60 * 6, json.dumps(rows))
        except Exception:
            pass
        return rows
    except Exception:
        logger.debug("fetch_games_by_season failed for %s %s", player_id, season, exc_info=True)
        return []


def fetch_career_games_by_id(player_id: int, seasons_start: int = 2000, seasons_end: int = 2025) -> List[dict]:
    if not player_id:
        return []

    aggregated: List[dict] = []
    for season in range(seasons_end, seasons_start - 1, -1):
        season_str = f"{season-1}-{str(season)[-2:]}" if season >= 2001 else f"{season}-{str(season+1)[-2:]}"
        rows = fetch_games_by_season(player_id, season_str)
        for r in rows or []:
            aggregated.append(r)
    # canonicalize_rows will dedupe by game_id/player_id when possible
    return canonicalize_rows(aggregated)


def get_player_season_stats(player_id: int, season: str) -> Dict[str, float]:
    if not player_id or not season:
        return {}

    cache_key = f"player_season:{player_id}:{season}"
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

    if playercareerstats is not None:
        try:
            def _pcs(pid):
                pcs = playercareerstats.PlayerCareerStats(player_id=pid)
                return pcs.get_data_frames()[0]

            df = _with_retries(_pcs, player_id)
            if df is None:
                return {}

            try:
                season_rows = df[df['SEASON_ID'] == season]
            except Exception:
                season_rows = []
                try:
                    for r in df.to_dict(orient='records'):
                        if r.get('SEASON_ID') == season:
                            season_rows.append(r)
                except Exception:
                    season_rows = []

            if hasattr(season_rows, 'empty') and season_rows.empty:
                stats = {}
            else:
                import pandas as _pd

                if not hasattr(season_rows, 'to_dict'):
                    df_season = _pd.DataFrame(season_rows)
                else:
                    df_season = season_rows if isinstance(season_rows, _pd.DataFrame) else _pd.DataFrame(season_rows)

                if df_season.empty:
                    stats = {}
                else:
                    stats = {}
                    for k in ('PTS', 'AST', 'REB'):
                        if k in df_season.columns:
                            try:
                                stats[k] = float(df_season[k].mean())
                            except Exception:
                                pass

            _local_cache[cache_key] = stats
            try:
                rc = _redis_client()
                if rc:
                    rc.setex(cache_key, 60 * 60 * 24, json.dumps(stats))
            except Exception:
                pass

            return stats
        except Exception:
            logger.debug('player season stats lookup failed for %s %s', player_id, season, exc_info=True)

    return {}


def get_team_stats(team_id: int) -> Dict[str, float]:
    if not team_id:
        return {}

    cache_key = f"team_stats:{team_id}"
    try:
        rc = _redis_client()
        if rc:
            raw = rc.get(cache_key)
            if raw:
                try:
                    return json.loads(raw) if not isinstance(raw, (bytes, bytearray)) else json.loads(raw.decode('utf-8'))
                except Exception:
                    pass
    except Exception:
        pass

    if cache_key in _local_cache:
        return _local_cache[cache_key]

    if teamgamelog is None:
        return {}

    try:
        def _fetch(tid):
            tg = teamgamelog.TeamGameLog(team_id=tid)
            return tg.get_data_frames()[0]

        df = _with_retries(_fetch, team_id)
        if df is None:
            return {}

        opp_cols = [c for c in ("OPP_PTS", "PTS_OPP", "OPPPTS", "PTS_ALLOWED") if c in df.columns]
        pts_col = "PTS" if "PTS" in df.columns else None

        if pts_col is None:
            return {}

        import pandas as _pd

        if isinstance(df, list):
            df = _pd.DataFrame(df)

        if df.empty:
            return {}

        stats: Dict[str, float] = {}
        try:
            stats["PTS_avg"] = float(df[pts_col].mean())
        except Exception:
            pass

        if opp_cols:
            try:
                stats["OPP_PTS_avg"] = float(df[opp_cols[0]].mean())
            except Exception:
                pass

        if "PTS_avg" in stats and "OPP_PTS_avg" in stats:
            try:
                stats["PTS_diff"] = float(stats["PTS_avg"] - stats["OPP_PTS_avg"])
            except Exception:
                pass

        _local_cache[cache_key] = stats
        try:
            rc = _redis_client()
            if rc:
                rc.setex(cache_key, 60 * 60 * 6, json.dumps(stats))
        except Exception:
            pass

        return stats
    except Exception:
        logger.debug("team stats lookup failed for %s", team_id, exc_info=True)

    return {}


__all__ = [
    "find_player_id_by_name",
    "find_player_id",
    "fetch_recent_games",
    "fetch_recent_games_by_id",
    "fetch_recent_games_by_name",
    "fetch_games_by_season",
    "fetch_career_games_by_id",
    "get_player_season_stats",
    "get_team_stats",
]

