"""Prototype helpers to compute season-level PER and Win Shares estimates
from aggregated game logs (play-by-play optional).

This module intentionally provides conservative approximations suitable for
feature-filling when LeagueDash endpoints are unavailable. It is a prototype
and should be validated against canonical sources before production use.
"""
from __future__ import annotations

import math
from typing import List, Dict, Optional

from backend.services import nba_stats_client
import os

# Tuned scale factors (apply to raw prototype estimates to better match canonical PER/WS).
# These were derived by offline validation and can be overridden via env vars.
PER_SCALE = float(os.environ.get('PER_WS_PER_SCALE', '0.34'))
WS_SCALE = float(os.environ.get('PER_WS_WS_SCALE', '0.31'))


def aggregate_season_games(games: List[Dict]) -> Dict[str, float]:
    """Aggregate per-game totals into season sums and per-game averages.

    Expects `games` to be a list of nba_api-style game dicts. Returns a dict
    with aggregated fields and games count.
    """
    count = 0
    sum_pts = sum_ast = sum_reb = 0.0
    sum_fga = sum_fgm = sum_fta = sum_ftm = 0.0
    sum_stl = sum_blk = sum_to = sum_min = 0.0

    for g in (games or []):
        try:
            count += 1
            sum_pts += float(g.get('PTS') or g.get('points') or 0)
            sum_ast += float(g.get('AST') or 0)
            sum_reb += float(g.get('REB') or 0)
            fga = g.get('FGA') if 'FGA' in g else g.get('FG_ATT') if 'FG_ATT' in g else 0
            fgm = g.get('FGM') if 'FGM' in g else 0
            fta = g.get('FTA') if 'FTA' in g else 0
            ftm = g.get('FTM') if 'FTM' in g else 0
            sum_fga += float(fga or 0)
            sum_fgm += float(fgm or 0)
            sum_fta += float(fta or 0)
            sum_ftm += float(ftm or 0)
            stl = g.get('STL') or g.get('stl') or 0
            blk = g.get('BLK') or g.get('blk') or 0
            tov = g.get('TO') or g.get('TOV') or g.get('to') or 0
            sum_stl += float(stl or 0)
            sum_blk += float(blk or 0)
            sum_to += float(tov or 0)
            mins = g.get('MIN') or g.get('min') or 0
            try:
                sum_min += float(mins)
            except Exception:
                # parse mm:ss
                try:
                    parts = str(mins).split(':')
                    if len(parts) == 2:
                        sum_min += float(parts[0]) + float(parts[1]) / 60.0
                except Exception:
                    pass
        except Exception:
            continue

    out = {
        'games': count,
        'PTS': sum_pts,
        'AST': sum_ast,
        'REB': sum_reb,
        'FGA': sum_fga,
        'FGM': sum_fgm,
        'FTA': sum_fta,
        'FTM': sum_ftm,
        'STL': sum_stl,
        'BLK': sum_blk,
        'TOV': sum_to,
        'MIN': sum_min,
    }

    # per-game averages
    if count > 0:
        for k in list(out.keys()):
            if k == 'games':
                continue
            out[f'{k}_per_game'] = out[k] / float(count)
    return out


def compute_per_ws_from_aggregates(agg: Dict[str, float]) -> Dict[str, Optional[float]]:
    """Compute approximate PER and Win Shares from aggregated season sums.

    This produces two fields: `PER_est` and `WS_est` (season totals). Values
    are approximate and should be validated.
    """
    games = int(agg.get('games') or 0)
    if games == 0:
        return {'PER_est': None, 'WS_est': None}

    # per-game values
    pts = agg.get('PTS_per_game') or 0.0
    ast = agg.get('AST_per_game') or 0.0
    reb = agg.get('REB_per_game') or 0.0
    stl = agg.get('STL_per_game') or 0.0
    blk = agg.get('BLK_per_game') or 0.0
    tov = agg.get('TOV_per_game') or 0.0
    fga = agg.get('FGA_per_game') or 0.0
    fgm = agg.get('FGM_per_game') or 0.0
    fta = agg.get('FTA_per_game') or 0.0
    ftm = agg.get('FTM_per_game') or 0.0
    mins = agg.get('MIN_per_game') or 0.0

    missed_fg = max(0.0, fga - fgm)
    missed_ft = max(0.0, fta - ftm)

    # per-game efficiency proxy
    eff = pts + reb + ast + stl + blk - missed_fg - missed_ft - tov

    # scale into PER-like magnitude (tunable). We choose a factor that places
    # typical efficiency values into the PER ~ 10-25 range. Apply tuned multiplier
    # to map prototype magnitudes closer to canonical PER values.
    per_est_raw = eff * 2.5
    per_est = per_est_raw * PER_SCALE

    # WS estimate: positive portion scaled to per-game WS then season total
    mins_factor = (mins / 30.0) if mins and mins > 0 else 1.0
    ws_per_game_raw = max(0.0, eff) * 0.018 * mins_factor
    ws_per_game = ws_per_game_raw * WS_SCALE
    ws_est = ws_per_game * games

    # clamp/sanity bounds
    try:
        per_est = float(per_est)
    except Exception:
        per_est = None
    try:
        ws_est = float(ws_est)
    except Exception:
        ws_est = None

    return {'PER_est': per_est, 'PER_est_raw': per_est_raw, 'WS_est': ws_est, 'WS_est_raw': ws_per_game_raw * games, 'eff_per_game': eff, 'ws_per_game': ws_per_game}


def compute_player_season_estimates(player_id: int, seasons: List[str]) -> Dict[str, Dict]:
    """Compute season-level PER/WS estimates for the provided seasons.

    Returns a mapping season -> estimates dict.
    """
    out = {}
    if not player_id or not seasons:
        return out

    for s in seasons:
        try:
            games = nba_stats_client.fetch_recent_games(player_id, limit=500, season=s)
            agg = aggregate_season_games(games)
            est = compute_per_ws_from_aggregates(agg)
            out[s] = {'aggregates': agg, 'estimates': est}
        except Exception as e:
            out[s] = {'error': str(e)}

    return out
