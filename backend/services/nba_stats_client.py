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
