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
    from nba_api.stats.static import teams as static_teams
    from nba_api.stats.endpoints import playergamelog
    from nba_api.stats.endpoints import teamgamelog
    from nba_api.stats.endpoints import leaguegamelog
    from nba_api.stats.endpoints import playercareerstats
    from nba_api.stats.endpoints import leaguedashplayerstats
except Exception:  # pragma: no cover - optional dep
    players = None
    static_teams = None
    playergamelog = None
    teamgamelog = None
    playercareerstats = None
    leaguedashplayerstats = None
    leaguegamelog = None


# In-process TTL cache as a fallback when Redis is unavailable
_local_cache = TTLCache(maxsize=2000, ttl=60 * 10)

# Simple token-bucket style rate limiter shared across sync calls
MAX_REQUESTS_PER_MINUTE = int(os.environ.get("NBA_API_MAX_RPM", "20"))
_tokens = float(MAX_REQUESTS_PER_MINUTE)
_last_refill = time.time()
_rl_lock = threading.Lock()

# Timeout for nba_api HTTP requests (seconds). Increase default to reduce transient read timeouts.
NBA_API_TIMEOUT = int(os.environ.get("NBA_API_TIMEOUT", "180"))


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


def _with_retries(fn, *args, retries: int = 8, backoff: float = 1.0, max_backoff: float = 120.0, **kwargs):
    """Invoke `fn` with retries, exponential backoff and jitter.

    - `retries`: number of attempts before giving up
    - `backoff`: initial backoff in seconds
    - `max_backoff`: cap for backoff
    """
    import random
    import requests
    import socket
    import ssl
    import urllib3
    from http.client import RemoteDisconnected as _RemoteDisconnected

    last_exc = None
    for attempt in range(retries):
        ok = _acquire_token(timeout=2.0)
        if not ok:
            # if token not available, wait a bit with jitter
            sleep_t = backoff * (attempt + 1) * (0.5 + random.random() * 0.5)
            time.sleep(min(sleep_t, max_backoff))
            continue
        try:
            # NOTE: Do NOT set global HTTP_PROXY/HTTPS_PROXY environment vars here.
            # Setting those breaks `nba_api`'s HTTPS calls when the configured
            # proxy cannot handle CONNECT tunnels (causes "Tunnel connection
            # failed: 400 Bad Request"). Prefer explicit REST proxying via the
            # local FastAPI service (callable by higher-level helpers) or let
            # `nba_api` make direct connections. If a proxy is desired for
            # specific HTTP requests, callers should use `requests` with the
            # `proxies=` parameter rather than mutating global env vars.
            return fn(*args, **kwargs)
        except Exception as e:
            last_exc = e
        except Exception as e:
            last_exc = e
            # If it's a connection-level error, increase backoff and jitter
            is_conn_err = False
            try:
                if isinstance(e, requests.exceptions.ConnectionError):
                    is_conn_err = True
                if isinstance(e, requests.exceptions.ReadTimeout):
                    is_conn_err = True
                if isinstance(e, requests.exceptions.ConnectTimeout):
                    is_conn_err = True
                if isinstance(e, urllib3.exceptions.ProtocolError):
                    is_conn_err = True
                if isinstance(e, ssl.SSLError):
                    is_conn_err = True
                if isinstance(e, socket.timeout):
                    is_conn_err = True
            except Exception:
                pass
            try:
                if isinstance(e, _RemoteDisconnected):
                    is_conn_err = True
            except Exception:
                pass

            # exponential backoff with larger cap for connection issues
            cap = max_backoff if is_conn_err else max_backoff / 2.0
            sleep_t = min(cap, backoff * (2 ** attempt))
            # add jitter
            sleep_t = sleep_t * (0.4 + random.random() * 0.8)
            time.sleep(sleep_t)
            continue
        finally:
            # no global proxy envs are modified in this function
            pass
    # final attempt without acquiring token
    try:
        # final attempt: small pause before final try
        time.sleep(backoff)
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
        # Prefer a cached all-players list via helper which already uses
        # Redis / local cache and also supports local-file fallback.
        allp = fetch_all_players()
    except Exception:
        try:
            # Last-resort: try direct call if available
            allp = players.get_players() if players is not None else []
        except Exception:
            allp = []

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


def fetch_recent_games(player_id: int, limit: int = 8, season: Optional[str] = None) -> List[dict]:
    """Fetch recent game logs for a player id. Returns list of raw game dicts.

    Tries Redis -> in-process TTLCache -> `nba_api` PlayerGameLog.
    Returns empty list when data isn't available.
    """
    if not player_id:
        return []

    cache_key = f"player_recent:{player_id}:{limit}:{season or 'any'}"

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
        def _fetch(pid, lim, seas):
            # nba_api has differing constructor signatures across versions; try several invocation patterns
            last_err = None
            try:
                if seas:
                    gl = playergamelog.PlayerGameLog(player_id=pid, season=seas, timeout=NBA_API_TIMEOUT)
                else:
                    gl = playergamelog.PlayerGameLog(player_id=pid, timeout=NBA_API_TIMEOUT)
            except TypeError as e:
                last_err = e
                try:
                    if seas:
                        gl = playergamelog.PlayerGameLog(player_id=pid, season=seas)
                    else:
                        gl = playergamelog.PlayerGameLog(player_id=pid)
                except TypeError as e2:
                    last_err = e2
                    try:
                        # positional fallback
                        if seas:
                            gl = playergamelog.PlayerGameLog(pid, seas)
                        else:
                            gl = playergamelog.PlayerGameLog(pid)
                    except Exception:
                        raise last_err
            df = gl.get_data_frames()[0]
            return df.head(lim).to_dict(orient="records")

        recent = _with_retries(_fetch, player_id, limit, season)
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
        try:
            # persist failed id for later retry
            _record_failed_fetch('player', player_id, 'fetch_recent_games')
        except Exception:
            pass
        return []


__all__ = [
    "find_player_id_by_name",
    "fetch_recent_games",
    "get_player_season_stats",
    "get_team_stats",
    "get_advanced_player_stats",
    "fetch_all_players",
    "fetch_all_teams",
    "fetch_full_player_history",
    "fetch_full_team_history",
    "fetch_season_league_player_game_logs",
]


def get_player_season_stats_multi(player_id: int, seasons: Optional[List[str]]) -> Dict[str, Dict[str, float]]:
    """Return a mapping season -> basic season stats for the given seasons list.

    If `seasons` is None or empty, returns an empty dict.
    """
    out = {}
    if not player_id or not seasons:
        return out
    for s in seasons:
        try:
            out[s] = get_player_season_stats(player_id, s) or {}
        except Exception:
            out[s] = {}
    return out


def fetch_all_players() -> List[dict]:
    """Return list of all players known to `nba_api.stats.static.players.get_players()`.

    Uses Redis/in-process cache when available. Returns empty list if dependency
    is not installed.
    """
    cache_key = "nba_all_players"
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

    if players is None:
        return []

    try:
        lst = _with_retries(players.get_players)
        _local_cache[cache_key] = lst
        try:
            rc = _redis_client()
            if rc:
                rc.setex(cache_key, 60 * 60 * 24, json.dumps(lst))
        except Exception:
            pass
        return lst
    except Exception:
        logger.exception("fetch_all_players failed")
        # Attempt to load a shipped/local cache file as a final fallback.
        try:
            repo_root = os.path.dirname(os.path.dirname(__file__))
            local_path = os.path.join(repo_root, 'data', 'all_players.json')
            if os.path.exists(local_path):
                with open(local_path, 'r', encoding='utf-8') as fh:
                    lst = json.load(fh)
                    _local_cache[cache_key] = lst
                    return lst
        except Exception:
            pass
        return []


def fetch_all_teams() -> List[dict]:
    """Return list of all teams from `nba_api.stats.static.teams.get_teams()`.

    Uses caching and safe fallback when dependency isn't installed.
    """
    cache_key = "nba_all_teams"
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

    if static_teams is None:
        return []

    try:
        lst = _with_retries(static_teams.get_teams)
        _local_cache[cache_key] = lst
        try:
            rc = _redis_client()
            if rc:
                rc.setex(cache_key, 60 * 60 * 24, json.dumps(lst))
        except Exception:
            pass
        return lst
    except Exception:
        logger.exception("fetch_all_teams failed")
        return []


def fetch_full_player_history(player_id: int, seasons: Optional[List[str]] = None) -> List[dict]:
    """Fetch and return aggregated game logs for a player over the provided seasons.

    Returns newest-first list of game dicts.
    """
    if not player_id:
        return []
    if not seasons:
        # default to current season only
        return fetch_recent_games(player_id, limit=500, season=None)
    return fetch_recent_games_multi(player_id, seasons, limit_per_season=82)


def fetch_full_team_history(team_id: int, seasons: Optional[List[str]] = None) -> List[dict]:
    """Fetch and return aggregated team game logs across seasons."""
    if not team_id:
        return []
    all_games = []
    if seasons:
        for s in seasons:
            try:
                g = fetch_team_games(team_id, limit=500, season=s)
                if g:
                    all_games.extend(g)
            except Exception:
                continue
    else:
        all_games = fetch_team_games(team_id, limit=500, season=None)

    try:
        all_games.sort(key=lambda g: g.get('GAME_DATE') or g.get('gameDate') or '', reverse=True)
    except Exception:
        pass
    return all_games


def get_team_stats_multi(team_id: int, seasons: Optional[List[str]]) -> Dict[str, Dict[str, float]]:
    """Return team stats per season for provided seasons."""
    out = {}
    if not team_id or not seasons:
        return out
    for s in seasons:
        try:
            out[s] = get_team_stats(team_id, s) or {}
        except Exception:
            out[s] = {}
    return out


def get_advanced_player_stats_multi(player_id: int, seasons: Optional[List[str]], use_fallback: bool = True) -> Dict[str, object]:
    """Aggregate advanced player stats across multiple seasons.

    Returns a dict with:
    - `per_season`: mapping season -> advanced stats dict
    - `aggregated`: averaged numeric values across seasons
    """
    result = {"per_season": {}, "aggregated": {}}
    if not player_id or not seasons:
        return result

    per_season = {}
    for s in seasons:
        try:
            stats = get_advanced_player_stats(player_id, s) or {}
            # fallback to computed metrics from game logs when LeagueDash is empty
            if not stats and use_fallback:
                try:
                    stats = get_advanced_player_stats_fallback(player_id, s) or {}
                except Exception:
                    stats = {}
            per_season[s] = stats
        except Exception:
            per_season[s] = {}

    # aggregate numeric columns by simple mean across seasons where present
    agg = {}
    counts = {}
    for s, stats in per_season.items():
        for k, v in (stats or {}).items():
            try:
                val = float(v)
            except Exception:
                continue
            agg[k] = agg.get(k, 0.0) + val
            counts[k] = counts.get(k, 0) + 1

    for k, total in agg.items():
        c = counts.get(k, 1)
        try:
            agg[k] = total / float(c)
        except Exception:
            agg[k] = total

    result["per_season"] = per_season
    result["aggregated"] = agg
    return result


def get_player_season_stats(player_id: int, season: str) -> Dict[str, float]:
    """Return basic season averages for a player (PTS/AST/REB) for a given season id.

    Tries Redis -> local cache -> `playercareerstats` endpoint. Returns an
    empty dict when data is unavailable. The `season` string should match the
    `SEASON_ID` values used by `nba_api` (e.g. '2024-25').
    """
    if not player_id or not season:
        return {}

    # When running in offline/dev mode prefer computing simple season stats
    # from available game logs instead of calling external `playercareerstats`.
    try:
        if os.environ.get('NBA_FORCE_FALLBACK', '') == '1':
            try:
                games = fetch_recent_games(player_id, limit=500, season=season)
                if not games:
                    return {}
                sum_pts = 0.0
                cnt = 0
                for g in games:
                    v = None
                    for k in ('PTS', 'points'):
                        if k in g and g.get(k) is not None:
                            try:
                                v = float(g.get(k))
                            except Exception:
                                v = None
                            break
                    if v is not None:
                        sum_pts += v
                        cnt += 1
                if cnt == 0:
                    return {}
                return {'PTS': sum_pts / cnt}
            except Exception:
                return {}
    except Exception:
        pass

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

    # Try playercareerstats if available
    if playercareerstats is not None:
        try:
            def _pcs(pid):
                    # PlayerCareerStats may accept different arg patterns across nba_api versions
                    last_err = None
                    try:
                        pcs = playercareerstats.PlayerCareerStats(player_id=pid, timeout=NBA_API_TIMEOUT)
                        return pcs.get_data_frames()[0]
                    except TypeError as e:
                        last_err = e
                    try:
                        pcs = playercareerstats.PlayerCareerStats(player_id=pid)
                        return pcs.get_data_frames()[0]
                    except TypeError:
                        pass
                    try:
                        pcs = playercareerstats.PlayerCareerStats(pid)
                        return pcs.get_data_frames()[0]
                    except Exception:
                        # re-raise the most helpful error to trigger retry/backoff
                        if last_err:
                            raise last_err
                        raise

            df = _with_retries(_pcs, player_id)
            # Expect df to be a DataFrame-like object
            if df is None:
                return {}

            # Filter by season id
            try:
                season_rows = df[df['SEASON_ID'] == season]
            except Exception:
                # If df indexing fails, fall back to scanning rows
                season_rows = []
                try:
                    for r in df.to_dict(orient='records'):
                        if r.get('SEASON_ID') == season:
                            season_rows.append(r)
                except Exception:
                    season_rows = []

            # If season_rows is empty or DataFrame-like with no rows, return {}
            if hasattr(season_rows, 'empty') and season_rows.empty:
                stats = {}
            else:
                # Compute basic means
                import pandas as _pd

                if not hasattr(season_rows, 'to_dict'):
                    # season_rows is a list of dicts
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

            # persist to caches
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

    # Not available
    return {}


def get_team_stats(team_id: int, season: Optional[str] = None) -> Dict[str, float]:
    """Placeholder: return basic team-level metrics if available.

    Currently returns an empty dict when data sources are not present.
    This is a small helper to be expanded later to call `teamgamelog` or
    other endpoints to compute offensive/defensive ratings.
    """
    if not team_id:
        return {}

    cache_key = f"team_stats:{team_id}:{season or 'any'}"
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

    # Try to fetch team game logs and compute simple averages (PTS / OPP)
    if teamgamelog is None:
        return {}

    try:
        def _fetch(tid, s):
            # Only pass `season` when truthy; some nba_api versions
            # expect the argument to be omitted rather than None.
            if s:
                tg = teamgamelog.TeamGameLog(team_id=tid, season=s, timeout=NBA_API_TIMEOUT)
            else:
                tg = teamgamelog.TeamGameLog(team_id=tid, timeout=NBA_API_TIMEOUT)
            return tg.get_data_frames()[0]

        df = _with_retries(_fetch, team_id, season)
        if df is None:
            return {}

        # Normalize column names - common variants for opponent points
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

        # Additional derived metrics when columns available
        # Games count
        try:
            stats['games'] = int(len(df))
        except Exception:
            pass

        # Field goal and free throw percentages if present
        try:
            fgm_col = None
            fga_col = None
            for c in ("FGM", "FGM_HOME", "FGM_AWAY"):
                if c in df.columns:
                    fgm_col = c
                    break
            for c in ("FGA", "FGA_HOME", "FGA_AWAY"):
                if c in df.columns:
                    fga_col = c
                    break
            if fgm_col and fga_col:
                try:
                    stats['FG_pct'] = float(df[fgm_col].sum()) / float(df[fga_col].sum()) if float(df[fga_col].sum()) > 0 else None
                except Exception:
                    pass
        except Exception:
            pass

        try:
            ftm_col = None
            fta_col = None
            for c in ("FTM", "FTM_HOME", "FTM_AWAY"):
                if c in df.columns:
                    ftm_col = c
                    break
            for c in ("FTA", "FTA_HOME", "FTA_AWAY"):
                if c in df.columns:
                    fta_col = c
                    break
            if ftm_col and fta_col:
                try:
                    stats['FT_pct'] = float(df[ftm_col].sum()) / float(df[fta_col].sum()) if float(df[fta_col].sum()) > 0 else None
                except Exception:
                    pass
        except Exception:
            pass

        # persist to caches
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


def fetch_team_games(team_id: int, limit: int = 500, season: Optional[str] = None) -> List[dict]:
    """Fetch recent team game logs. Returns list of raw game dicts.

    Uses Redis/local cache and `teamgamelog.TeamGameLog` when available.
    """
    if not team_id:
        return []

    cache_key = f"team_games:{team_id}:{limit}:{season or 'any'}"
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

    # Check for deterministic cached logs under repo for CI/tests
    try:
        repo_root = os.path.dirname(os.path.dirname(__file__))
        cached_dir = os.path.join(repo_root, 'data', 'cached_game_logs')
        if season:
            cached_path = os.path.join(cached_dir, f"team_{team_id}_{season}.json")
        else:
            cached_path = os.path.join(cached_dir, f"team_{team_id}.json")
        if os.path.exists(cached_path):
            try:
                with open(cached_path, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                    _local_cache[cache_key] = data
                    return data
            except Exception:
                pass

    except Exception:
        pass

    if cache_key in _local_cache:
        return _local_cache[cache_key]

    if teamgamelog is None:
        return []

    try:
        def _fetch(tid, lim, s):
            if s:
                tg = teamgamelog.TeamGameLog(team_id=tid, season=s)
            else:
                tg = teamgamelog.TeamGameLog(team_id=tid)
            df = tg.get_data_frames()[0]
            return df.head(lim).to_dict(orient='records')

        recent = _with_retries(_fetch, team_id, limit, season)
        _local_cache[cache_key] = recent
        try:
            rc = _redis_client()
            if rc:
                rc.setex(cache_key, 60 * 10, json.dumps(recent))
        except Exception:
            pass
        return recent
    except Exception:
        logger.exception("Error fetching team games for team_id=%s", team_id)
        try:
            _record_failed_fetch('team', team_id, 'fetch_team_games')
        except Exception:
            pass
        return []


def get_advanced_team_stats_fallback(team_id: int, season: Optional[str]) -> Dict[str, float]:
    """Compute basic team advanced-like stats from season game logs.

    Returns PTS_avg, OPP_PTS_avg, PTS_diff, games, and TS-like metrics
    aggregated at the team level when available.
    """
    if not team_id or not season:
        return {}

    cache_key = f"team_advanced_fallback:{team_id}:{season}"
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

    games = []
    try:
        games = fetch_team_games(team_id, limit=500, season=season)
    except Exception:
        games = []

    if not games:
        return {}

    count = 0
    sum_pts = 0.0
    sum_opp = 0.0
    sum_fga = 0.0
    sum_fgm = 0.0
    sum_fta = 0.0
    sum_ftm = 0.0

    for g in games:
        try:
            count += 1
            # Team PTS column variants
            pts = g.get('PTS') if 'PTS' in g else g.get('TEAM_PTS') if 'TEAM_PTS' in g else None
            opp = g.get('OPP_PTS') if 'OPP_PTS' in g else g.get('PTS_OPP') if 'PTS_OPP' in g else None
            if pts is not None:
                sum_pts += float(pts)
            if opp is not None:
                sum_opp += float(opp)

            fga = g.get('FGA') if 'FGA' in g else None
            fgm = g.get('FGM') if 'FGM' in g else None
            fta = g.get('FTA') if 'FTA' in g else None
            ftm = g.get('FTM') if 'FTM' in g else None

            if fga is not None:
                try:
                    sum_fga += float(fga)
                except Exception:
                    pass
            if fgm is not None:
                try:
                    sum_fgm += float(fgm)
                except Exception:
                    pass
            if fta is not None:
                try:
                    sum_fta += float(fta)
                except Exception:
                    pass
            if ftm is not None:
                try:
                    sum_ftm += float(ftm)
                except Exception:
                    pass
        except Exception:
            continue

    if count == 0:
        return {}

    stats = {}
    stats['games'] = count
    stats['PTS_avg'] = sum_pts / count
    stats['OPP_PTS_avg'] = sum_opp / count if sum_opp else None
    if stats.get('OPP_PTS_avg') is not None:
        stats['PTS_diff'] = stats['PTS_avg'] - stats['OPP_PTS_avg']
    else:
        stats['PTS_diff'] = None

    try:
        stats['FG_pct'] = (sum_fgm / sum_fga) if sum_fga > 0 else None
    except Exception:
        stats['FG_pct'] = None

    try:
        stats['FT_pct'] = (sum_ftm / sum_fta) if sum_fta > 0 else None
    except Exception:
        stats['FT_pct'] = None

    # persist
    _local_cache[cache_key] = stats
    try:
        rc = _redis_client()
        if rc:
            rc.setex(cache_key, 60 * 60 * 24, json.dumps(stats))
    except Exception:
        pass

    return stats


def fetch_recent_games_multi(player_id: int, seasons: Optional[List[str]] = None, limit_per_season: int = 82) -> List[dict]:
    """Fetch and aggregate recent games across multiple seasons.

    Returns games ordered newest-first across the provided seasons. If
    `seasons` is None or empty, returns an empty list.
    """
    if not player_id or not seasons:
        return []

    cache_key = f"player_recent_multi:{player_id}:{','.join(seasons)}:{limit_per_season}"
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

    # Aggregate per-season logs
    all_games = []
    try:
        for s in seasons:
            try:
                games = fetch_recent_games(player_id, limit_per_season, season=s)
                if games:
                    all_games.extend(games)
            except Exception:
                continue

        # Sort by date if GAME_DATE present (newest first)
        try:
            all_games.sort(key=lambda g: g.get('GAME_DATE') or g.get('gameDate') or '', reverse=True)
        except Exception:
            pass

        _local_cache[cache_key] = all_games
        try:
            rc = _redis_client()
            if rc:
                rc.setex(cache_key, 60 * 60 * 12, json.dumps(all_games))
        except Exception:
            pass

        return all_games
    except Exception:
        logger.exception("Error fetching recent games multi for player_id=%s", player_id)
        return []


def get_advanced_team_stats_multi(team_id: int, seasons: Optional[List[str]], use_fallback: bool = True) -> Dict[str, object]:
    """Return per-season and aggregated advanced-like team stats across seasons."""
    result = {"per_season": {}, "aggregated": {}}
    if not team_id or not seasons:
        return result
    per_season = {}
    for s in seasons:
        try:
            stats = get_team_stats(team_id, s) or {}
            if not stats and use_fallback:
                try:
                    stats = get_advanced_team_stats_fallback(team_id, s) or {}
                except Exception:
                    stats = {}
            per_season[s] = stats
        except Exception:
            per_season[s] = {}

    # aggregate numeric columns by mean
    agg = {}
    counts = {}
    for s, stats in per_season.items():
        for k, v in (stats or {}).items():
            try:
                val = float(v)
            except Exception:
                continue
            agg[k] = agg.get(k, 0.0) + val
            counts[k] = counts.get(k, 0) + 1

    for k, total in agg.items():
        c = counts.get(k, 1)
        try:
            agg[k] = total / float(c)
        except Exception:
            agg[k] = total

    result['per_season'] = per_season
    result['aggregated'] = agg
    return result


def get_advanced_player_stats(player_id: int, season: Optional[str]) -> Dict[str, float]:
    """Return advanced metrics for a player for a given season using LeagueDashPlayerStats.

    Uses `per_mode_simple='PerGame'` to request per-game metrics and extracts
    requested advanced columns. If `season` is falsy or the optional
    `leaguedashplayerstats` dependency is not installed this returns {}.
    """
    if not player_id or not season:
        return {}

    # Allow forcing fallback-only behavior to avoid external LeagueDash calls
    # when running in offline/dev environments or when the upstream API is
    # unstable. Set env `NBA_FORCE_FALLBACK=1` to enable.
    try:
        if os.environ.get('NBA_FORCE_FALLBACK', '') == '1':
            try:
                return get_advanced_player_stats_fallback(player_id, season) or {}
            except Exception:
                return {}
    except Exception:
        pass


    

    cache_key = f"player_advanced:{player_id}:{season}"
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

    if leaguedashplayerstats is None:
        return {}

    try:
        def _fetch(s):
            # `nba_api` has changed signatures across versions. Try several
            # invocation patterns for compatibility.
            last_err = None
            try:
                lds = leaguedashplayerstats.LeagueDashPlayerStats(season=s, per_mode_simple='PerGame', timeout=NBA_API_TIMEOUT)
                return lds.get_data_frames()[0]
            except TypeError as e:
                last_err = e
            try:
                lds = leaguedashplayerstats.LeagueDashPlayerStats(season=s, per_mode_simple='PerGame')
                return lds.get_data_frames()[0]
            except TypeError as e:
                last_err = e
            try:
                lds = leaguedashplayerstats.LeagueDashPlayerStats(season=s, per_mode='PerGame', timeout=NBA_API_TIMEOUT)
                return lds.get_data_frames()[0]
            except TypeError as e:
                last_err = e
            try:
                lds = leaguedashplayerstats.LeagueDashPlayerStats(season=s, timeout=NBA_API_TIMEOUT)
                return lds.get_data_frames()[0]
            except Exception as e:
                last_err = e
            # re-raise the last error to trigger outer retry/backoff
            raise last_err

        df_all = _with_retries(_fetch, season)
        if df_all is None or df_all.empty:
            return {}

        # Filter for the player row
        try:
            player_rows = df_all[df_all['PLAYER_ID'] == player_id]
        except Exception:
            player_rows = []

        if getattr(player_rows, 'empty', False) or not player_rows:
            return {}

        # Take first matching row
        if isinstance(player_rows, list):
            row = player_rows[0]
        else:
            row = player_rows.iloc[0]

        cols = ['PER', 'TS_PCT', 'USG_PCT', 'PIE', 'OFF_RATING', 'DEF_RATING']
        stats: Dict[str, float] = {}
        for col in cols:
            try:
                if isinstance(row, dict):
                    if col in row and row[col] is not None:
                        stats[col] = float(row[col])
                else:
                    if col in row.index and row[col] is not None:
                        stats[col] = float(row[col])
            except Exception:
                pass

        # persist
        _local_cache[cache_key] = stats
        try:
            rc = _redis_client()
            if rc:
                rc.setex(cache_key, 60 * 60 * 24, json.dumps(stats))
        except Exception:
            pass

        return stats
    except Exception:
        logger.debug('advanced player stats lookup failed for %s %s', player_id, season, exc_info=True)
        return {}


def fetch_league_player_advanced(season: str) -> Dict[int, Dict[str, float]]:
    """Fetch LeagueDashPlayerStats for the whole league for `season` and
    return a mapping PLAYER_ID -> stats dict.

    Uses caching and falls back to empty dict when dependency unavailable.
    """
    out = {}
    if not season:
        return out

    cache_key = f"league_player_advanced:{season}"
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

    if leaguedashplayerstats is None:
        return out

    try:
        def _fetch(s):
            last_err = None
            try:
                lds = leaguedashplayerstats.LeagueDashPlayerStats(season=s, per_mode_simple='PerGame', timeout=NBA_API_TIMEOUT)
                return lds.get_data_frames()[0]
            except TypeError as e:
                last_err = e
            try:
                lds = leaguedashplayerstats.LeagueDashPlayerStats(season=s, per_mode_simple='PerGame')
                return lds.get_data_frames()[0]
            except TypeError as e:
                last_err = e
            try:
                lds = leaguedashplayerstats.LeagueDashPlayerStats(season=s, per_mode='PerGame', timeout=NBA_API_TIMEOUT)
                return lds.get_data_frames()[0]
            except TypeError as e:
                last_err = e
            try:
                lds = leaguedashplayerstats.LeagueDashPlayerStats(season=s, timeout=NBA_API_TIMEOUT)
                return lds.get_data_frames()[0]
            except Exception as e:
                last_err = e
            raise last_err

        df_all = _with_retries(_fetch, season)
        if df_all is None:
            return out

        # normalize to mapping
        try:
            rows = df_all.to_dict(orient='records')
        except Exception:
            rows = []

        for r in (rows or []):
            pid = r.get('PLAYER_ID') or r.get('player_id')
            if not pid:
                continue
            stats = {}
            for col in ('PER', 'TS_PCT', 'USG_PCT', 'PIE', 'OFF_RATING', 'DEF_RATING'):
                if col in r and r.get(col) is not None:
                    try:
                        stats[col] = float(r.get(col))
                    except Exception:
                        pass
            out[int(pid)] = stats

        # persist
        try:
            _local_cache[cache_key] = out
            rc = _redis_client()
            if rc:
                rc.setex(cache_key, 60 * 60 * 24, json.dumps(out))
        except Exception:
            pass

        return out
    except Exception:
        logger.exception('fetch_league_player_advanced failed for %s', season)
        return {}


def fetch_season_league_player_game_logs(season: str) -> Dict[int, List[dict]]:
    """Fetch league-level player game logs for a season and return mapping
    PLAYER_ID -> list of game dicts (newest-first).

    Uses `leaguegamelog.LeagueGameLog` when available to retrieve a single
    table containing player game logs for the whole league for the season,
    drastically reducing per-player HTTP calls.
    """
    out = {}
    if not season:
        return out


    def get_player_name_by_id(player_id: int, seasons: Optional[List[str]] = None) -> Optional[str]:
        """Resolve a player name given a numeric NBA player id.

        Strategy:
        - Check Redis / in-process cache
        - Use `fetch_all_players()` to find a matching id
        - If seasons provided, use `fetch_season_league_player_game_logs` to find a PLAYER_NAME
        - Return None if unresolved
        """
        if not player_id:
            return None

        cache_key = f"player_name:{player_id}"
        try:
            rc = _redis_client()
            if rc:
                raw = rc.get(cache_key)
                if raw:
                    try:
                        return raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
                    except Exception:
                        return str(raw)
        except Exception:
            pass

        if cache_key in _local_cache:
            return _local_cache[cache_key]

        # 1) scan all players
        try:
            allp = fetch_all_players() or []
            for p in allp:
                try:
                    if int(p.get('id')) == int(player_id):
                        name = p.get('full_name') or p.get('fullName') or p.get('display_name')
                        if name:
                            _local_cache[cache_key] = name
                            try:
                                rc = _redis_client()
                                if rc:
                                    rc.setex(cache_key, 60 * 60 * 24, name)
                            except Exception:
                                pass
                            return name
                except Exception:
                    continue
        except Exception:
            pass

        # 2) use league-level season logs if available
        try:
            seasons_to_try = seasons or []
            for s in seasons_to_try:
                try:
                    lg = fetch_season_league_player_game_logs(s)
                    games = lg.get(int(player_id))
                    if games and len(games) > 0:
                        # attempt to extract PLAYER_NAME from a game row
                        rn = games[0].get('PLAYER_NAME') or games[0].get('player_name') or games[0].get('PLAYER')
                        if rn:
                            _local_cache[cache_key] = rn
                            try:
                                rc = _redis_client()
                                if rc:
                                    rc.setex(cache_key, 60 * 60 * 24, rn)
                            except Exception:
                                pass
                            return rn
                except Exception:
                    continue
        except Exception:
            pass

        return None

    cache_key = f"league_player_games:{season}"
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

    if leaguegamelog is None:
        return out

    try:
        def _fetch(s):
            lg = leaguegamelog.LeagueGameLog(season=s, timeout=NBA_API_TIMEOUT)
            return lg.get_data_frames()[0]

        df = _with_retries(_fetch, season)
        if df is None:
            return out

        try:
            rows = df.to_dict(orient='records')
        except Exception:
            rows = []

        for r in (rows or []):
            # PLAYER_ID variants
            pid = r.get('PLAYER_ID') or r.get('player_id')
            if not pid:
                continue
            try:
                pid = int(pid)
            except Exception:
                continue
            if pid not in out:
                out[pid] = []
            out[pid].append(r)

        # sort each player's list newest-first if date available
        for pid, games in out.items():
            try:
                games.sort(key=lambda g: g.get('GAME_DATE') or g.get('GAME_DATE_EST') or g.get('gameDate') or '', reverse=True)
            except Exception:
                pass

        # persist
        try:
            _local_cache[cache_key] = out
            rc = _redis_client()
            if rc:
                rc.setex(cache_key, 60 * 60 * 12, json.dumps(out))
        except Exception:
            pass

        return out
    except Exception:
        logger.exception('fetch_season_league_player_game_logs failed for %s', season)
        return {}


def _record_failed_fetch(kind: str, entity_id: int, reason: str) -> None:
    """Append a failed fetch record to a local retry queue file for later retry."""
    try:
        repo_root = os.path.dirname(os.path.dirname(__file__))
        failed_path = os.path.join(repo_root, 'data', 'failed_nba_fetches.jsonl')
        rec = {'kind': kind, 'id': int(entity_id) if entity_id is not None else None, 'reason': reason}
        with open(failed_path, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(rec) + '\n')
    except Exception:
        logger.debug('failed to record failed fetch for %s %s', kind, entity_id, exc_info=True)


def get_advanced_player_stats_fallback(player_id: int, season: Optional[str]) -> Dict[str, float]:
    """Derive advanced-like metrics from season game logs when league dash data
    is unavailable. Computes TS%, FG%, 3P%, FT%, PTS/AST/REB per game and games count.
    """
    if not player_id or not season:
        return {}

    cache_key = f"player_advanced_fallback:{player_id}:{season}"
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

    # fetch full season logs (larger limit)
    games = []
    try:
        games = fetch_recent_games(player_id, limit=500, season=season)
    except Exception:
        games = []

    if not games:
        return {}

    # aggregate available columns
    count = 0
    sum_pts = 0.0
    sum_ast = 0.0
    sum_reb = 0.0
    sum_fga = 0.0
    sum_fgm = 0.0
    sum_fg3m = 0.0
    sum_fg3a = 0.0
    sum_fta = 0.0
    sum_ftm = 0.0
    sum_stl = 0.0
    sum_blk = 0.0
    sum_to = 0.0
    sum_min = 0.0

    for g in games:
        try:
            count += 1
            sum_pts += float(g.get('PTS') or g.get('PTS', 0) or 0)
            sum_ast += float(g.get('AST') or 0)
            sum_reb += float(g.get('REB') or 0)
            # many nba_api versions use different keys; attempt variants
            fga = g.get('FGA') if 'FGA' in g else g.get('FG_ATT') if 'FG_ATT' in g else None
            fgm = g.get('FGM') if 'FGM' in g else None
            fg3m = g.get('FG3M') if 'FG3M' in g else None
            fg3a = g.get('FG3A') if 'FG3A' in g else None
            fta = g.get('FTA') if 'FTA' in g else None
            ftm = g.get('FTM') if 'FTM' in g else None

            if fga is not None:
                try:
                    sum_fga += float(fga)
                except Exception:
                    pass
            if fgm is not None:
                try:
                    sum_fgm += float(fgm)
                except Exception:
                    pass
            if fg3m is not None:
                try:
                    sum_fg3m += float(fg3m)
                except Exception:
                    pass
            if fg3a is not None:
                try:
                    sum_fg3a += float(fg3a)
                except Exception:
                    pass
            if fta is not None:
                try:
                    sum_fta += float(fta)
                except Exception:
                    pass
            if ftm is not None:
                try:
                    sum_ftm += float(ftm)
                except Exception:
                    pass
            # optional defensive / turnover / minutes fields
            try:
                stl = g.get('STL') if 'STL' in g else g.get('stl') if 'stl' in g else None
                if stl is not None:
                    sum_stl += float(stl)
            except Exception:
                pass
            try:
                blk = g.get('BLK') if 'BLK' in g else g.get('blk') if 'blk' in g else None
                if blk is not None:
                    sum_blk += float(blk)
            except Exception:
                pass
            try:
                tov = g.get('TO') if 'TO' in g else g.get('TOV') if 'TOV' in g else g.get('to') if 'to' in g else None
                if tov is not None:
                    sum_to += float(tov)
            except Exception:
                pass
            try:
                mins = g.get('MIN') if 'MIN' in g else g.get('min') if 'min' in g else None
                if mins is not None:
                    # MIN may be '36:12' format in some logs; attempt float conversion
                    try:
                        sum_min += float(mins)
                    except Exception:
                        # try parsing mm:ss
                        try:
                            parts = str(mins).split(':')
                            if len(parts) == 2:
                                sum_min += float(parts[0]) + float(parts[1]) / 60.0
                        except Exception:
                            pass
            except Exception:
                pass
        except Exception:
            continue

    if count == 0:
        return {}

    stats = {}
    stats['games'] = count
    stats['PTS_per_game'] = sum_pts / count
    stats['AST_per_game'] = sum_ast / count
    stats['REB_per_game'] = sum_reb / count

    # FG%
    try:
        stats['FG_pct'] = (sum_fgm / sum_fga) if sum_fga > 0 else None
    except Exception:
        stats['FG_pct'] = None

    # 3P%
    try:
        stats['FG3_pct'] = (sum_fg3m / sum_fg3a) if sum_fg3a > 0 else None
    except Exception:
        stats['FG3_pct'] = None

    # FT%
    try:
        stats['FT_pct'] = (sum_ftm / sum_fta) if sum_fta > 0 else None
    except Exception:
        stats['FT_pct'] = None

    # True Shooting % approx if we have FGA and FTA
    try:
        if sum_fga > 0:
            ts = sum_pts / (2.0 * (sum_fga + 0.44 * sum_fta))
            stats['TS_PCT'] = float(ts)
        else:
            stats['TS_PCT'] = None
    except Exception:
        stats['TS_PCT'] = None
    # Prefer using the play-by-play prototype estimator for PER/WS fallbacks
    # when available. This centralizes the prototype logic and ensures tuned
    # scale factors are applied consistently.
    try:
        from backend.services import per_ws_from_playbyplay

        try:
            agg = per_ws_from_playbyplay.aggregate_season_games(games)
            est = per_ws_from_playbyplay.compute_per_ws_from_aggregates(agg)
            # copy back useful fields into stats
            stats['PER_proxy'] = est.get('PER_est_raw') or None
            stats['PER'] = est.get('PER_est')
            stats['WS_proxy_per_game'] = est.get('ws_per_game') or None
            stats['WS'] = est.get('WS_est')
            # keep raw aggregates for debugging
            stats.update({'_per_ws_agg_games': agg.get('games', 0)})
        except Exception:
            # fallback: leave PER/WS absent
            stats['PER_proxy'] = None
            stats['PER'] = None
            stats['WS_proxy_per_game'] = None
            stats['WS'] = None
    except Exception:
        # If prototype module not importable, leave proxies absent
        stats['PER_proxy'] = None
        stats['PER'] = None
        stats['WS_proxy_per_game'] = None
        stats['WS'] = None

    # persist to caches
    _local_cache[cache_key] = stats
    try:
        rc = _redis_client()
        if rc:
            rc.setex(cache_key, 60 * 60 * 24, json.dumps(stats))
    except Exception:
        pass

    return stats
