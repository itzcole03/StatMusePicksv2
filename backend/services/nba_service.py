"""Higher-level NBA context service for backend usage.

This module wraps `nba_stats_client` and the shared cache helpers to
provide structured player summaries and batch context builders that other
backend services can call. It mirrors the shape returned by the HTTP
endpoint `/player_summary` so callers (and tests) can use it directly.
"""
from __future__ import annotations

import json
import time
import logging
from typing import List, Dict, Any, Optional

from backend.services import nba_stats_client
from backend.services.cache import get_redis

logger = logging.getLogger(__name__)


STAT_MAP = {
    'points': 'PTS', 'pts': 'PTS',
    'assists': 'AST', 'ast': 'AST',
    'rebounds': 'REB', 'reb': 'REB',
    'stl': 'STL', 'steals': 'STL',
    'blk': 'BLK', 'blocks': 'BLK',
}


def _redis_client():
    return get_redis()


def get_player_summary(player: str, stat: str = 'points', limit: int = 8, debug: bool = False) -> Dict[str, Any]:
    """Return a structured player summary dict (sync).

    Attempts to read/write Redis when available; otherwise uses the
    `nba_stats_client` functions and returns a best-effort summary.
    """
    cache_key = f"player_summary:{player}:{stat}:{limit}"

    # Try redis cache first
    try:
        rc = _redis_client()
        if rc:
            raw = rc.get(cache_key)
            if raw:
                data = json.loads(raw.decode('utf-8') if isinstance(raw, (bytes, bytearray)) else raw)
                data['cached'] = True
                return data
    except Exception:
        logger.debug('redis unavailable for player_summary cache', exc_info=True)

    # Build summary using nba_stats_client
    pid = nba_stats_client.find_player_id_by_name(player)
    debug_info = {'player_query': player, 'found_player_id': pid}
    if not pid:
        raise ValueError('player not found')

    recent = nba_stats_client.fetch_recent_games(pid, limit)
    debug_info['recent_count'] = len(recent)

    recent_games: List[Dict[str, Any]] = []
    stat_field = STAT_MAP.get(stat.lower(), stat.upper())
    vals: List[float] = []
    for g in recent:
        val = g.get(stat_field) if stat_field and stat_field in g else None
        recent_games.append({
            'gameDate': g.get('GAME_DATE'),
            'matchup': g.get('MATCHUP'),
            'statValue': val,
            'raw': g,
        })
        try:
            if val is not None:
                vals.append(float(val))
        except Exception:
            pass

    season_avg = (sum(vals) / len(vals)) if vals else None
    recent_text = None
    if recent_games:
        sample_vals = [str(g['statValue']) if g['statValue'] is not None else 'null' for g in recent_games]
        recent_text = f"Last {len(recent_games)} games {stat}: {', '.join(sample_vals)}"

    last_game_date = None
    last_season = None
    if recent_games:
        try:
            last_game_date = recent_games[0].get('gameDate')
        except Exception:
            last_game_date = None
    else:
        # best-effort: try to infer last season via nba_stats_client if available
        try:
            if nba_stats_client.playercareerstats is not None:  # type: ignore[attr-defined]
                pcs = nba_stats_client.playercareerstats.PlayerCareerStats(player_id=pid)  # type: ignore[attr-defined]
                dfpcs = pcs.get_data_frames()[0]
                if not dfpcs.empty and 'SEASON_ID' in dfpcs.columns:
                    s = dfpcs['SEASON_ID'].tolist()
                    last_season = s[0] if s else None
        except Exception:
            last_season = None

    out: Dict[str, Any] = {
        'player': player,
        'stat': stat,
        'league': 'nba',
        'recent': recent_text,
        'recentGames': recent_games,
        'seasonAvg': round(season_avg, 2) if season_avg is not None else None,
        'lastGameDate': last_game_date,
        'lastSeason': last_season,
        'fetchedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    }

    if not recent_games:
        out['noGamesThisSeason'] = True
        out['note'] = 'No recent games available for this player this season.'

    if debug:
        out['debug'] = debug_info

    # persist to redis if available
    try:
        rc = _redis_client()
        if rc:
            rc.setex(cache_key, 60 * 60 * 6, json.dumps(out))
    except Exception:
        pass

    return out


def build_external_context_for_projections(items: List[Dict[str, Any]], stat: str = 'points', limit: int = 8) -> List[Dict[str, Any]]:
    """Given a list of projection items (each must include a `player` key),
    return a list of player summary contexts aligned with the input order.

    Items that cannot be resolved will include an `error` field instead of
    a full context object so callers can handle partial results.
    """
    results: List[Dict[str, Any]] = []
    for it in items:
        player = it.get('player') or it.get('player_name')
        if not player:
            results.append({'error': 'missing player', 'input': it})
            continue
        try:
            ctx = get_player_summary(player, stat=stat, limit=limit, debug=False)
            results.append(ctx)
        except Exception as e:
            results.append({'player': player, 'error': str(e)})
    return results


__all__ = ['get_player_summary', 'build_external_context_for_projections']
