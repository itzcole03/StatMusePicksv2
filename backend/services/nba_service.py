"""Higher-level NBA context service for backend usage.

This module wraps `nba_stats_client` and the shared cache helpers to
provide structured player summaries and batch context builders that other
backend services can call. It mirrors the shape returned by the HTTP
endpoint `/player_summary` so callers (and tests) can use it directly.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from backend.services import nba_stats_client
from backend.services.cache import get_redis

logger = logging.getLogger(__name__)


STAT_MAP = {
    "points": "PTS",
    "pts": "PTS",
    "assists": "AST",
    "ast": "AST",
    "rebounds": "REB",
    "reb": "REB",
    "stl": "STL",
    "steals": "STL",
    "blk": "BLK",
    "blocks": "BLK",
}


def _redis_client():
    return get_redis()


def get_player_summary(
    player: str,
    stat: str = "points",
    limit: int = 8,
    season: Optional[str] = None,
    debug: bool = False,
) -> Dict[str, Any]:
    """Return a structured player summary dict (sync).

    Attempts to read/write Redis when available; otherwise uses the
    `nba_stats_client` functions and returns a best-effort summary.
    """
    cache_key = f"player_summary:{player}:{stat}:{limit}:{season or 'any'}"

    # Try redis cache first
    try:
        rc = _redis_client()
        if rc:
            raw = rc.get(cache_key)
            if raw:
                data = json.loads(
                    raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
                )
                data["cached"] = True
                return data
    except Exception:
        logger.debug("redis unavailable for player_summary cache", exc_info=True)

    # Build summary using nba_stats_client
    pid = nba_stats_client.find_player_id_by_name(player)
    debug_info = {"player_query": player, "found_player_id": pid}
    if not pid:
        raise ValueError("player not found")

    recent = nba_stats_client.fetch_recent_games(pid, limit, season)
    debug_info["recent_count"] = len(recent)

    recent_games: List[Dict[str, Any]] = []
    stat_field = STAT_MAP.get(stat.lower(), stat.upper())
    vals: List[float] = []
    for g in recent:
        val = g.get(stat_field) if stat_field and stat_field in g else None
        recent_games.append(
            {
                "gameDate": g.get("GAME_DATE"),
                "matchup": g.get("MATCHUP"),
                "statValue": val,
                "raw": g,
            }
        )
        try:
            if val is not None:
                vals.append(float(val))
        except Exception:
            pass

    season_avg = (sum(vals) / len(vals)) if vals else None
    recent_text = None
    if recent_games:
        sample_vals = [
            str(g["statValue"]) if g["statValue"] is not None else "null"
            for g in recent_games
        ]
        recent_text = f"Last {len(recent_games)} games {stat}: {', '.join(sample_vals)}"

    last_game_date = None
    last_season = None
    if recent_games:
        try:
            last_game_date = recent_games[0].get("gameDate")
        except Exception:
            last_game_date = None
    else:
        # best-effort: try to infer last season via nba_stats_client if available
        try:
            if nba_stats_client.playercareerstats is not None:  # type: ignore[attr-defined]
                pcs = nba_stats_client.playercareerstats.PlayerCareerStats(player_id=pid)  # type: ignore[attr-defined]
                dfpcs = pcs.get_data_frames()[0]
                if not dfpcs.empty and "SEASON_ID" in dfpcs.columns:
                    s = dfpcs["SEASON_ID"].tolist()
                    last_season = s[0] if s else None
        except Exception:
            last_season = None

    out: Dict[str, Any] = {
        "player": player,
        "stat": stat,
        "league": "nba",
        "recent": recent_text,
        "recentGames": recent_games,
        "seasonAvg": round(season_avg, 2) if season_avg is not None else None,
        "lastGameDate": last_game_date,
        "lastSeason": last_season,
        "fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    if not recent_games:
        out["noGamesThisSeason"] = True
        out["note"] = "No recent games available for this player this season."

    if debug:
        out["debug"] = debug_info

    # Attach advanced player metrics when available
    try:
        adv = nba_stats_client.get_advanced_player_stats(pid, season)
        if adv:
            out["advanced"] = adv
    except Exception:
        pass

    # persist to redis if available
    try:
        rc = _redis_client()
        if rc:
            rc.setex(cache_key, 60 * 60 * 6, json.dumps(out))
    except Exception:
        pass

    return out


def build_external_context_for_projections(
    items: List[Dict[str, Any]], stat: str = "points", limit: int = 8
) -> List[Dict[str, Any]]:
    """Given a list of projection items (each must include a `player` key),
    return a list of player summary contexts aligned with the input order.

    Items that cannot be resolved will include an `error` field instead of
    a full context object so callers can handle partial results.
    """
    results: List[Dict[str, Any]] = []
    for it in items:
        player = it.get("player") or it.get("player_name")
        season = it.get("season") or None
        if not player:
            results.append({"error": "missing player", "input": it})
            continue
        try:
            ctx = get_player_summary(
                player, stat=stat, limit=limit, season=season, debug=False
            )
            results.append(ctx)
        except Exception as e:
            results.append({"player": player, "error": str(e)})
    return results


__all__ = [
    "get_player_summary",
    "build_external_context_for_projections",
    "get_player_context_for_training",
]


def get_player_context_for_training(
    player: str,
    stat: str,
    game_date: str,
    season: str,
) -> Dict[str, Any]:
    """Dedicated function to fetch all necessary context for a single training sample.

    This explicitly requests season-scoped data and returns a compact, structured
    context used by ML training pipelines.
    """
    if not player or not season:
        raise ValueError("player and season are required")

    cache_key = f"player_training:{player}:{season}:{stat}:{game_date}"
    try:
        rc = _redis_client()
        if rc:
            raw = rc.get(cache_key)
            if raw:
                try:
                    data = json.loads(
                        raw.decode("utf-8")
                        if isinstance(raw, (bytes, bytearray))
                        else raw
                    )
                    data["cached"] = True
                    return data
                except Exception:
                    pass
    except Exception:
        logger.debug("redis unavailable for player_training cache", exc_info=True)

    pid = nba_stats_client.find_player_id_by_name(player)
    if not pid:
        raise ValueError(f"Player not found: {player}")

    # 1. Player Game Log (fetch entire season to allow post-filtering by game_date)
    recent_games_season = nba_stats_client.fetch_recent_games(pid, 82, season)

    # 2. Season Stats (for the season)
    season_stats = nba_stats_client.get_player_season_stats(pid, season)

    # 3. Advanced Stats (for the season)
    advanced_stats = nba_stats_client.get_advanced_player_stats(pid, season)

    # --- Multi-season context enhancements ---
    # Build a seasons list including the requested season and up to two prior seasons
    seasons_list: List[str] = []
    if season:
        seasons_list.append(season)
        try:
            start = int(season.split("-")[0])
            prev1 = f"{start-1}-{(start)%100:02d}"
            prev2 = f"{start-2}-{(start-1)%100:02d}"
            seasons_list.append(prev1)
            seasons_list.append(prev2)
        except Exception:
            # If parsing fails, fall back to single-season list
            pass

    # Trim duplicates and keep order
    seasons_list = [
        s for i, s in enumerate(seasons_list) if s and s not in seasons_list[:i]
    ]

    # Multi-season player-level stats
    try:
        season_stats_multi = (
            nba_stats_client.get_player_season_stats_multi(pid, seasons_list)
            if seasons_list
            else {}
        )
    except Exception:
        season_stats_multi = {}

    try:
        advanced_stats_multi = (
            nba_stats_client.get_advanced_player_stats_multi(pid, seasons_list)
            if seasons_list
            else {}
        )
    except Exception:
        advanced_stats_multi = {}

    # Attempt to infer team id from recent games (if present) and fetch team-level multi-season stats
    team_id = None
    try:
        if recent_games_season:
            # many nba_api rows include 'TEAM_ID'
            first = recent_games_season[0]
            team_id = (
                first.get("TEAM_ID")
                or first.get("team_id")
                or first.get("TEAM_ID_HOME")
            )
            if team_id:
                try:
                    team_id = int(team_id)
                except Exception:
                    team_id = None
    except Exception:
        team_id = None

    team_stats_multi = {}
    team_advanced_multi = {}
    if team_id and seasons_list:
        try:
            team_stats_multi = (
                nba_stats_client.get_team_stats_multi(team_id, seasons_list) or {}
            )
        except Exception:
            team_stats_multi = {}
        try:
            team_advanced_multi = (
                nba_stats_client.get_advanced_team_stats_multi(team_id, seasons_list)
                or {}
            )
        except Exception:
            team_advanced_multi = {}

    out: Dict[str, Any] = {
        "player": player,
        "playerId": pid,
        "season": season,
        "stat": stat,
        "gameDate": game_date,
        "recentGamesRaw": recent_games_season,
        "seasonStats": season_stats,
        "advancedStats": advanced_stats,
        "seasonStatsMulti": season_stats_multi,
        "advancedStatsMulti": advanced_stats_multi,
        "seasonsConsidered": seasons_list,
        "teamId": team_id,
        "teamStatsMulti": team_stats_multi,
        "teamAdvancedMulti": team_advanced_multi,
        "fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    try:
        rc = _redis_client()
        if rc:
            rc.setex(cache_key, 60 * 60 * 24, json.dumps(out))
    except Exception:
        pass

    return out
