"""Helper wrappers around `nba_api` (swar/nba_api) to fetch season and career game logs.

These functions are best-effort and include retries and simple rate-limiting.
They are intended for dev/test use and are guarded so environments without
`nba_api` won't fail import.
"""
from __future__ import annotations

import time
from typing import List, Dict
from backend.services.nba_normalize import canonicalize_rows

try:
    from nba_api.stats.static import players as _players
    from nba_api.stats.endpoints import playergamelog as _playergamelog
    HAS_NBA_API = True
except Exception:
    _players = None
    _playergamelog = None
    HAS_NBA_API = False


def _normalize_season(season: int) -> str:
    # produce '2024-25' style string for nba_api
    return f"{season-1}-{str(season)[-2:]}" if season >= 2001 else f"{season}-{str(season+1)[-2:]}"


def find_player_id(player_name: str):
    if not HAS_NBA_API:
        return None
    try:
        matches = _players.find_players_by_full_name(player_name)
        if matches:
            return matches[0]["id"] if isinstance(matches[0], dict) else matches[0].get("id")
    except Exception:
        pass

    try:
        # fallback to scanning all players
        for p in _players.get_players():
            if p.get("full_name", "").lower() == player_name.lower():
                return p.get("id")
            if player_name.lower() in p.get("full_name", "").lower():
                return p.get("id")
    except Exception:
        pass

    return None


def fetch_games_by_season(player_id: int, season_str: str, retries: int = 3, backoff: float = 0.5) -> List[Dict]:
    if not HAS_NBA_API or player_id is None:
        return []
    attempt = 0
    while attempt < retries:
        attempt += 1
        try:
            pgl = _playergamelog.PlayerGameLog(player_id=player_id, season=season_str)
            dfs = pgl.get_data_frames()
            if not dfs:
                return []
            df = dfs[0]
            return canonicalize_rows(df.to_dict(orient="records"))
        except Exception:
            time.sleep(backoff * attempt)
            continue
    return []


def fetch_career_games_by_id(player_id: int, seasons_start: int = 2000, seasons_end: int = 2025) -> List[Dict]:
    if not HAS_NBA_API or player_id is None:
        return []
    rows = []
    for season in range(seasons_end, seasons_start - 1, -1):
        season_str = _normalize_season(season)
        part = fetch_games_by_season(player_id, season_str)
        for r in part or []:
            rows.append(r)
        # polite pause
        time.sleep(0.6)
    return canonicalize_rows(rows)
