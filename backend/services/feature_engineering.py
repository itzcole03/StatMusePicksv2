"""Feature engineering helpers for the backend.

This module contains a small, well-tested set of helpers used by the
prediction service and training code. Functions are intentionally small and
pure to make unit-testing easy and to allow them to be used in DataFrame
pipelines later.

Key concepts provided here:
- recent statistics (mean, median, std, trend slope)
- rolling / windowed averages and a small EMA implementation
- a thin wrapper that returns a flat feature dict suitable for model input
- a DataFrame-oriented `engineer_features` used by training scripts

Behavioral notes:
- Functions expect lists of lightweight dict objects representing recent
  games where the field `statValue` (or another `stat_field`) contains the
  numeric stat. Missing or None values are ignored when computing means.
- The module defines an explicit `is_back_to_back` indicator derived from
  `contextualFactors.daysRest` (1 when daysRest == 0, else 0). This is
  surfaced for both the dict-oriented and DataFrame-oriented wrappers.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np


def recent_stats_from_games(
    recent_games: List[Dict[str, Any]], stat_field: str = "statValue"
) -> Dict[str, Optional[float]]:
    """Compute simple recent statistics from a list of game records.

    Args:
        recent_games: Sequence of game dicts. Each dict should provide the
            numeric stat under `stat_field` (or None/missing).
        stat_field: Key name to read the numeric stat from each game dict.

    Returns:
        A dictionary with keys: ``mean``, ``median``, ``std``, ``sample_size``
        and ``trend_slope``. Numeric values are floats; when no samples
                    'trade_sentiment': float(llm_feats.get('trade_sentiment') or llm_feats.get('trade_sent') or 0.0),
        exist the mean/median/std/trend_slope values are ``None`` and
        ``sample_size`` is 0.

    Notes:
        - ``trend_slope`` is computed with a simple 1-D linear fit (numpy
          polyfit) over the observed samples in chronological order.
        - This function intentionally avoids complex imputation so the
          caller can decide how to fall back (e.g. to season averages).
    """
    values = [g.get(stat_field) for g in recent_games if g.get(stat_field) is not None]
    values = [float(v) for v in values]
    n = len(values)
    if n == 0:
        return {
            "mean": None,
            "median": None,
            "std": None,
            "sample_size": 0,
            "trend_slope": None,
        }

    arr = np.array(values)
    mean = float(arr.mean())
    median = float(np.median(arr))
    std = float(arr.std(ddof=0))

    trend_slope = None
    if n >= 2:
        x = np.arange(n)
        # simple linear fit
        slope, _ = np.polyfit(x, arr, 1)
        trend_slope = float(slope)

    return {
        "mean": mean,
        "median": median,
        "std": std,
        "sample_size": n,
        "trend_slope": trend_slope,
    }


def rolling_averages(
    recent_games: List[Dict[str, Any]], stat_field: str = "statValue"
) -> Dict[str, Optional[float]]:
    """Compute a few small rolling statistics from recent games.

    The function returns a dict containing the last 3/5/10 averages and an
    exponential moving average with alpha=0.3. Missing values are ignored.
    """
    vals = [g.get(stat_field) for g in recent_games if g.get(stat_field) is not None]
    vals = [float(v) for v in vals]

    def avg(slice_vals):
        return float(np.mean(slice_vals)) if len(slice_vals) > 0 else None

    return {
        "last3": avg(vals[:3]) if len(vals) >= 1 else None,
        "last5": avg(vals[:5]) if len(vals) >= 1 else None,
        "last10": avg(vals[:10]) if len(vals) >= 1 else None,
        "ema_alpha_0_3": _ema(vals, 0.3) if len(vals) >= 1 else None,
    }


def _ema(values: List[float], alpha: float) -> Optional[float]:
    """Compute a simple exponential moving average (EMA).

    This is a tiny, dependency-free implementation used for quick
    experimentation. It returns ``None`` for empty input.
    """
    if not values:
        return None
    ema = values[0]
    for v in values[1:]:
        ema = alpha * v + (1 - alpha) * ema
    return float(ema)


# --- Contextual feature helpers (Phase 3 additions) ----------------------
TEAM_COORDS = {
    # abbrev: (lat, lon, altitude_m)
    "ATL": (33.755, -84.39, 313),
    "BOS": (42.366, -71.062, 14),
    "BKN": (40.682, -73.975, 10),
    "CHA": (35.226, -80.84, 241),
    "CHI": (41.88, -87.63, 181),
    "CLE": (41.43, -81.69, 207),
    "DAL": (32.79, -96.77, 140),
    "DEN": (39.748, -104.996, 1609),
    "DET": (42.7, -83.054, 181),
    "GSW": (37.768, -122.387, 16),
    "HOU": (29.75, -95.36, 13),
    "IND": (39.76, -86.15, 218),
    "LAC": (33.96, -118.14, 89),
    "LAL": (34.043, -118.267, 89),
    "MEM": (35.138, -90.05, 99),
    "MIA": (25.78, -80.22, 2),
    "MIL": (43.045, -87.917, 188),
    "MIN": (44.98, -93.27, 264),
    "NOP": (29.948, -90.08, 2),
    "NYK": (40.75, -73.993, 10),
    "OKC": (35.463, -97.516, 370),
    "ORL": (28.539, -81.383, 26),
    "PHI": (39.901, -75.171, 12),
    "PHX": (33.445, -112.07, 331),
    "POR": (45.52, -122.665, 15),
    "SAC": (38.580, -121.499, 9),
    "SAS": (29.427, -98.437, 198),
    "TOR": (43.643, -79.379, 76),
    "UTA": (40.768, -111.901, 1288),
    "WAS": (38.898, -77.02, 6),
}

# Common rivalry pairs (unordered)
RIVAL_PAIRS = set(
    [
        frozenset(("LAL", "LAC")),
        frozenset(("LAL", "BOS")),
        frozenset(("NYK", "BOS")),
        frozenset(("GSW", "LAL")),
        frozenset(("PHI", "NYK")),
        frozenset(("BKN", "NYK")),
    ]
)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in kilometers between two lat/lon points."""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _get_team_coords(abbrev: Optional[str]):
    if not abbrev:
        return None
    try:
        key = str(abbrev).upper()
        return TEAM_COORDS.get(key)
    except Exception:
        return None


def _is_rival(team_abbrev: Optional[str], opp_abbrev: Optional[str]) -> bool:
    if not team_abbrev or not opp_abbrev:
        return False
    try:
        t = str(team_abbrev).upper()
        o = str(opp_abbrev).upper()
        return frozenset((t, o)) in RIVAL_PAIRS
    except Exception:
        return False


def _add_contextual_features(
    features: Dict[str, Any],
    player_ctx: Dict[str, Any],
    opponent_ctx: Optional[Dict[str, Any]] = None,
):
    """Enrich features dict with contextual features: playoff, rivalry, national TV, travel distance, altitude."""
    ctx = player_ctx.get("contextualFactors") or {}
    # Playoff flag
    is_playoff = bool(
        ctx.get("isPlayoff")
        or ctx.get("gameType") == "Playoffs"
        or player_ctx.get("gameType") == "Playoffs"
    )
    features["is_playoff"] = 1 if is_playoff else 0

    # National TV / big game indicator
    national = bool(
        ctx.get("isNationalTV") or ctx.get("nationalTelecast") or ctx.get("isNational")
    )
    features["is_national_tv"] = 1 if national else 0

    # Rivalry
    team_abbrev = (
        ctx.get("teamAbbrev")
        or player_ctx.get("team")
        or player_ctx.get("teamAbbrev")
        or player_ctx.get("teamId")
    )
    opp_abbrev = None
    if opponent_ctx:
        opp_abbrev = (
            opponent_ctx.get("abbrev")
            or opponent_ctx.get("team")
            or opponent_ctx.get("teamId")
        )
    else:
        opp_abbrev = ctx.get("opponentAbbrev") or player_ctx.get("opponent")
    features["is_rivalry"] = 1 if _is_rival(team_abbrev, opp_abbrev) else 0

    # Travel distance (km) between team and opponent home arenas (approx)
    coords_team = _get_team_coords(team_abbrev)
    coords_opp = _get_team_coords(opp_abbrev)
    travel_km = 0.0
    opp_alt = 0.0
    if coords_team and coords_opp:
        try:
            travel_km = float(
                _haversine_km(
                    coords_team[0], coords_team[1], coords_opp[0], coords_opp[1]
                )
            )
            opp_alt = float(coords_opp[2] or 0.0)
        except Exception:
            travel_km = 0.0
            opp_alt = float(coords_opp[2] if coords_opp else 0.0)

    features["travel_distance_km"] = travel_km
    features["opp_altitude_m"] = opp_alt
    features["is_high_altitude_opp"] = 1 if opp_alt >= 1000 else 0

    # Add contextual Phase 3 features (playoff, rivalry, national TV, travel, altitude)
    try:
        _add_contextual_features(features, player_context, None)
    except Exception:
        pass
    return features


# -------------------------------------------------------------------------


def engineer_features(player_context: Dict[str, Any]) -> Dict[str, Any]:
    """High-level feature engineering wrapper returning a flat dict.

    Args:
        player_context: A mapping representing a player's context. Expected
            keys include ``recentGames`` (list of game dicts) and
            optionally ``seasonAvg`` and ``contextualFactors``.

    Returns:
        A flat dictionary of features suitable for quick model inputs. The
        returned dict uses simple imputation: missing numeric values are
        set to ``0.0``. The explicit ``is_back_to_back`` key is provided
        and derived from ``contextualFactors.daysRest`` (1 when daysRest == 0).
    """
    recent = player_context.get("recentGames", []) or []
    stats = recent_stats_from_games(recent)
    rolls = rolling_averages(recent)

    features = {
        "recent_mean": stats["mean"] or player_context.get("seasonAvg"),
        "recent_median": stats["median"],
        "recent_std": stats["std"] or 0.0,
        "sample_size": stats["sample_size"],
        "trend_slope": stats["trend_slope"] or 0.0,
        "last3_avg": rolls["last3"] or player_context.get("seasonAvg"),
        "last5_avg": rolls["last5"] or player_context.get("seasonAvg"),
        "last10_avg": rolls["last10"] or player_context.get("seasonAvg"),
        "ema_0_3": rolls["ema_alpha_0_3"] or player_context.get("seasonAvg"),
        # back-to-back indicator: 1 when daysRest == 0, else 0 (derived from contextualFactors)
        "is_back_to_back": (
            1
            if (player_context.get("contextualFactors", {}).get("daysRest") == 0)
            else 0
        ),
    }

    # Simple imputation for missing numeric values
    for k, v in list(features.items()):
        if v is None:
            features[k] = 0.0

    # Multi-season aggregated features (if provided by backend context)
    multi_adv = player_context.get("advancedStatsMulti") or {}
    multi_season_stats = player_context.get("seasonStatsMulti") or {}
    try:
        adv_agg = multi_adv.get("aggregated", {}) if isinstance(multi_adv, dict) else {}
    except Exception:
        adv_agg = {}

    # seasonStatsMulti is mapping season->stats; compute simple mean across seasons
    season_agg = {}
    try:
        counts = {}
        sums = {}
        for s, st in (multi_season_stats or {}).items():
            if not isinstance(st, dict):
                continue
            for k, v in st.items():
                try:
                    fv = float(v)
                except Exception:
                    continue
                sums[k] = sums.get(k, 0.0) + fv
                counts[k] = counts.get(k, 0) + 1
        for k, total in sums.items():
            season_agg[k] = total / float(counts.get(k, 1))
    except Exception:
        season_agg = {}

    features.update(
        {
            # prefer canonical advanced fields, fall back to computed proxies when present
            "multi_PER": float(adv_agg.get("PER") or adv_agg.get("PER_proxy") or 0.0),
            "multi_WS": float(
                adv_agg.get("WS") or adv_agg.get("WS_proxy_per_game") or 0.0
            ),
            "multi_TS_PCT": float(adv_agg.get("TS_PCT") or 0.0),
            "multi_USG_PCT": float(adv_agg.get("USG_PCT") or 0.0),
            "multi_season_PTS_avg": float(season_agg.get("PTS") or 0.0),
            "multi_season_count": (
                int(len(multi_season_stats))
                if isinstance(multi_season_stats, dict)
                else 0
            ),
        }
    )
    # Include multi-season BPM when available (or 0.0)
    try:
        multi_bpm = (
            adv_agg.get("BPM")
            or adv_agg.get("BPM_48")
            or adv_agg.get("BPM_approx")
            or 0.0
        )
    except Exception:
        multi_bpm = 0.0
    features.update(
        {
            "multi_BPM": float(multi_bpm),
        }
    )
    # Additional advanced/team aggregated metrics
    features.update(
        {
            "multi_PIE": float(adv_agg.get("PIE") or 0.0),
            "multi_off_rating": float(adv_agg.get("OFF_RATING") or 0.0),
            "multi_def_rating": float(adv_agg.get("DEF_RATING") or 0.0),
        }
    )

    # Attempt league-level normalization (z-score) for advanced stats when
    # a season can be inferred from the provided multi-season stats. This
    # helps make proxies more comparable across players and seasons.
    try:
        from backend.services import nba_stats_client as _nba

        season_to_use = None
        if isinstance(multi_season_stats, dict) and len(multi_season_stats) > 0:
            # pick most recent season key if available
            try:
                season_to_use = list(multi_season_stats.keys())[0]
            except Exception:
                season_to_use = None

        if season_to_use:
            league_map = _nba.fetch_league_player_advanced(season_to_use)
            if league_map:
                # compute league mean/std for PER and TS_PCT when available
                per_vals = []
                ts_vals = []
                pts_vals = []
                for pid, stats in league_map.items():
                    try:
                        if "PER" in stats:
                            per_vals.append(float(stats["PER"]))
                    except Exception:
                        pass
                    try:
                        if "TS_PCT" in stats:
                            ts_vals.append(float(stats["TS_PCT"]))
                    except Exception:
                        pass
                    try:
                        # some league mappings include per-game PTS under other keys; skip if absent
                        if "PTS" in stats:
                            pts_vals.append(float(stats["PTS"]))
                    except Exception:
                        pass

                import math

                def _z(v, vals):
                    try:
                        if v is None:
                            return 0.0
                        if not vals:
                            return 0.0
                        mean = float(sum(vals) / len(vals))
                        var = float(sum((x - mean) ** 2 for x in vals) / len(vals))
                        std = math.sqrt(var) if var > 0.0 else 0.0
                        return float((v - mean) / std) if std > 0.0 else 0.0
                    except Exception:
                        return 0.0

                # produce z-scored features for PER and TS_PCT
                try:
                    features["multi_PER_z"] = _z(features.get("multi_PER"), per_vals)
                except Exception:
                    features["multi_PER_z"] = 0.0
                try:
                    features["multi_TS_pct_z"] = _z(
                        features.get("multi_TS_PCT"), ts_vals
                    )
                except Exception:
                    features["multi_TS_pct_z"] = 0.0
    except Exception:
        # non-fatal; if normalization fails just continue with raw features
        pass
    # Player-context features (contract year, All-Star, recent awards, trade sentiment)
    try:
        # contract end year heuristics
        contract = player_context.get("contract") or {}
        end_year = (
            contract.get("end_year")
            or contract.get("contractEndYear")
            or player_context.get("contractEndYear")
        )
        current_year = datetime.now().year
        is_contract_year = 0
        try:
            if end_year is not None:
                if int(end_year) in (current_year, current_year + 1):
                    is_contract_year = 1
        except Exception:
            is_contract_year = 0
        features["is_contract_year"] = is_contract_year

        # All-Star indicator
        is_all_star = (
            1
            if (
                player_context.get("isAllStar")
                or player_context.get("allStar")
                or player_context.get("all_star")
            )
            else 0
        )
        features["is_all_star"] = is_all_star

        # Recent awards count (list expected under 'awards')
        awards = player_context.get("awards") or []
        try:
            features["recent_awards_count"] = int(len(awards))
        except Exception:
            features["recent_awards_count"] = 0

        # Trade rumor / transfer sentiment from existing LLM extraction if available
        # Reuse previously-extracted llm_feats when present in player_context
        llm_feats = player_context.get("llm_features") or {}
        trade_sent = 0.0
        try:
            trade_sent = float(
                llm_feats.get("trade_sentiment") or llm_feats.get("trade_sent") or 0.0
            )
        except Exception:
            trade_sent = 0.0
        features["trade_sentiment"] = trade_sent
    except Exception:
        # non-fatal
        features["is_contract_year"] = 0
        features["is_all_star"] = 0
        features["recent_awards_count"] = 0
        features["trade_sentiment"] = 0.0

    # Add contextual Phase 3 features (playoff, rivalry, national TV, travel, altitude)
    try:
        _add_contextual_features(features, player_context, None)
    except Exception:
        pass

    return features


"""Feature engineering helpers for player predictions.

This module provides lightweight functions used by the ML service and
eventually the training pipeline. Keep functions pure and data-frame
friendly so they can be tested independently.
"""
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

# Opt-in to pandas future behavior to avoid the downcasting warning during fillna
try:
    pd.set_option("future.no_silent_downcasting", True)
except Exception:
    # Older pandas versions may not provide this option; ignore failures.
    pass


def calculate_rolling_averages(
    recent_games: List[Dict], windows: List[int] = [3, 5, 10]
) -> Dict:
    values = [
        g.get("statValue") for g in recent_games if g.get("statValue") is not None
    ]
    out = {}
    for w in windows:
        if w > 0 and len(values) > 0:
            slice_vals = values[:w] if len(values) >= w else values[: len(values)]
            out[f"last_{w}_avg"] = float(np.mean(slice_vals))
        else:
            out[f"last_{w}_avg"] = None

    # exponential moving average
    if values:
        alpha = 0.3
        ema = values[0]
        for v in values[1:]:
            ema = alpha * v + (1 - alpha) * ema
        out["exponential_moving_avg"] = float(ema)
    else:
        out["exponential_moving_avg"] = None

    # weighted moving average (more weight to recent games)
    def weighted_moving_avg(vals: List[float], window: int) -> Optional[float]:
        if not vals or window <= 0:
            return None
        window_len = min(window, len(vals))
        slice_vals = vals[:window_len]
        weights = np.arange(window_len, 0, -1)
        wsum = float(np.dot(slice_vals, weights))
        denom = float(weights.sum())
        return float(wsum / denom) if denom != 0.0 else None

    out["wma_3"] = weighted_moving_avg(values, 3)
    out["wma_5"] = weighted_moving_avg(values, 5)

    # rolling statistics: std, min, max, median over windows
    for w in windows:
        key_base = f"last_{w}"
        if len(values) >= 1:
            slice_vals = values[:w] if len(values) >= w else values[: len(values)]
            arr = np.array(slice_vals, dtype=float)
            out[f"{key_base}_std"] = float(arr.std(ddof=0)) if arr.size > 0 else None
            out[f"{key_base}_min"] = float(arr.min()) if arr.size > 0 else None
            out[f"{key_base}_max"] = float(arr.max()) if arr.size > 0 else None
            out[f"{key_base}_median"] = float(np.median(arr)) if arr.size > 0 else None
        else:
            out[f"{key_base}_std"] = None
            out[f"{key_base}_min"] = None
            out[f"{key_base}_max"] = None
            out[f"{key_base}_median"] = None

    # trend slope (linear regression) over last 10 games (or available)
    def linear_slope(vals: List[float], window: int = 10) -> Optional[float]:
        if not vals:
            return None
        slice_vals = vals[:window]
        if len(slice_vals) < 2:
            return 0.0
        x = np.arange(len(slice_vals))
        y = np.array(slice_vals, dtype=float)
        slope, _ = np.polyfit(x, y, 1)
        return float(slope)

    out["slope_10"] = linear_slope(values, 10)

    # momentum: current (most recent) vs 5-game average
    if values:
        current = float(values[0])
        if len(values) >= 5:
            five_avg = float(np.mean(values[:5]))
        else:
            five_avg = float(np.mean(values))
        out["momentum_vs_5_avg"] = float(current - five_avg)
    else:
        out["momentum_vs_5_avg"] = None

    return out


def _compute_rolling_stats_for_player(player_data: Dict) -> Dict:
    """Helper wrapper used by `engineer_features` returning recent mean/std plus rolling metrics.

    Preserves the original keys used by `engineer_features`: `recent_mean`, `recent_std`
    and merges the output of `calculate_rolling_averages`.
    """
    recent = player_data.get("recentGames") or []
    vals = [g.get("statValue") for g in recent if g.get("statValue") is not None]
    out = {"recent_mean": None, "recent_std": None}
    if vals:
        out["recent_mean"] = float(np.mean(vals))
        out["recent_std"] = float(np.std(vals))
    out.update(calculate_rolling_averages(recent))
    return out


def _compute_contextual_for_player(player_data: Dict) -> Dict:
    """Compute simple contextual fields used by `engineer_features`.

    Returns keys: `season_avg`, `is_home`, `days_rest`, `is_back_to_back`.
    """
    ctx = player_data.get("contextualFactors", {}) or {}
    season_avg = player_data.get("seasonAvg")
    is_home = 1 if ctx.get("homeAway") == "home" else 0
    days_rest = ctx.get("daysRest") or 0
    is_back_to_back = 1 if days_rest == 0 else 0
    return {
        "season_avg": season_avg,
        "is_home": is_home,
        "days_rest": days_rest,
        "is_back_to_back": is_back_to_back,
    }


def _temporal_and_phase3_enrichment(features: Dict, player_data: Dict, opponent_data: Optional[Dict]) -> Dict:
    """Enrich `features` with opponent-adjusted stats, contextual flags, advanced metrics, LLM features, and tracking features.

    This mirrors the Phase-3 wiring in `engineer_features` but is isolated for testing.
    """
    # Advanced metrics (PER, TS%, USG%, ORtg/DRtg) fetched when available
    try:
        from backend.services.advanced_metrics_service import (
            create_default_service as _create_adv,
        )

        adv_svc = _create_adv()
        pid = (
            player_data.get("player_id")
            or player_data.get("playerId")
            or player_data.get("playerName")
        )
        if pid:
            try:
                adv = adv_svc.fetch_advanced_metrics(str(pid))
                if adv:
                    features["adv_PER"] = float(adv.get("PER") or 0.0)
                    features["adv_WS"] = float(adv.get("WS") or 0.0)
                    features["adv_TS_pct"] = float(adv.get("TS_pct") or 0.0)
                    features["adv_USG_pct"] = float(adv.get("USG_pct") or 0.0)
                    features["adv_ORtg"] = float(adv.get("ORtg") or 0.0)
                    features["adv_DRtg"] = float(adv.get("DRtg") or 0.0)
                    try:
                        features["adv_BPM"] = float(
                            adv.get("BPM")
                            or adv.get("BPM_48")
                            or adv.get("BPM_approx")
                            or 0.0
                        )
                    except Exception:
                        features["adv_BPM"] = 0.0
            except Exception:
                pass
    except Exception:
        pass

    try:
        # LLM-derived qualitative features: injury sentiment, morale, motivation
        from backend.services.llm_feature_service import (
            create_default_service as _create_llm,
        )

        llm_svc = _create_llm()

        def _text_fetcher(name: str) -> str:
            return player_data.get("news_summary") or player_data.get("news") or ""

        pname = (
            player_data.get("playerName")
            or player_data.get("player_name")
            or str(player_data.get("player_id") or "")
        )
        try:
            # Prefer structured JSON path
            text_context = _text_fetcher(pname)
            if hasattr(llm_svc, "extract_from_text"):
                try:
                    structured = llm_svc.extract_from_text(pname, text_context)
                except Exception:
                    structured = None
                if structured:
                    features.update(
                        {
                            "injury_sentiment": float(
                                structured.get("news_sentiment") or 0.0
                            ),
                            "morale_score": float(
                                structured.get("morale_score") or 0.0
                            ),
                            "motivation": float(
                                structured.get("motivation") or 0.0
                            ),
                            "trade_sentiment": float(
                                structured.get("trade_sentiment") or 0.0
                            ),
                        }
                    )
                    raise StopIteration

            llm_feats = llm_svc.fetch_news_and_extract(pname, "news_v1", _text_fetcher)
            if llm_feats:
                features.update(
                    {
                        "injury_sentiment": float(
                            llm_feats.get("injury_sentiment") or 0.0
                        ),
                        "morale_score": float(llm_feats.get("morale_score") or 0.0),
                        "motivation": float(llm_feats.get("motivation") or 0.0),
                        "trade_sentiment": float(
                            llm_feats.get("trade_sentiment")
                            or llm_feats.get("trade_sent")
                            or 0.0
                        ),
                    }
                )
        except StopIteration:
            pass
        except Exception:
            pass
    except Exception:
        pass

    # opponent features (optional)
    if opponent_data:
        features["opp_def_rating"] = opponent_data.get("defensiveRating")
        features["opp_pace"] = opponent_data.get("pace")
    else:
        features["opp_def_rating"] = None
        features["opp_pace"] = None

    # Opponent-adjusted features
    adv = _calculate_opponent_adjusted(player_data.get("recentGames") or [], opponent_data)
    features.update(adv)

    # Phase 3: tracking features
    try:
        from backend.services.player_tracking_service import (
            features_for_player as _trk_features_for_player,
        )

        pname = (
            player_data.get("playerName")
            or player_data.get("player_name")
            or player_data.get("playerId")
            or player_data.get("player_id")
            or None
        )
        if pname:
            try:
                tr_feats = _trk_features_for_player(str(pname), seasons=None)
                if isinstance(tr_feats, dict):
                    for k, v in tr_feats.items():
                        try:
                            features[f"trk_{k}"] = float(v) if v is not None else 0.0
                        except Exception:
                            features[f"trk_{k}"] = 0.0
            except Exception:
                pass
    except Exception:
        pass

    # Add contextual Phase 3 features (playoff, rivalry, national TV, travel, altitude)
    try:
        _add_contextual_features(features, player_data, opponent_data)
    except Exception:
        pass

    return features


def engineer_features(
    player_data: Dict, opponent_data: Optional[Dict] = None
) -> pd.DataFrame:
    # rolling/recent stats helper
    rolling_block = _compute_rolling_stats_for_player(player_data)

    # contextual helper
    contextual_block = _compute_contextual_for_player(player_data)

    features = {}
    features.update(rolling_block)
    features.update(contextual_block)
    # recent games list (new variable used by opponent-adjusted helpers)
    recent = player_data.get("recentGames") or []

    # Multi-season aggregated features (if present on the player_data)
    multi_adv = player_data.get("advancedStatsMulti") or {}
    multi_season_stats = player_data.get("seasonStatsMulti") or {}
    try:
        adv_agg = multi_adv.get("aggregated", {}) if isinstance(multi_adv, dict) else {}
    except Exception:
        adv_agg = {}

    # Aggregate seasonStatsMulti simple mean across seasons
    season_agg = {}
    try:
        sums = {}
        counts = {}
        for s, st in (multi_season_stats or {}).items():
            if not isinstance(st, dict):
                continue
            for k, v in st.items():
                try:
                    fv = float(v)
                except Exception:
                    continue
                sums[k] = sums.get(k, 0.0) + fv
                counts[k] = counts.get(k, 0) + 1
        for k, total in sums.items():
            season_agg[k] = total / float(counts.get(k, 1))
    except Exception:
        season_agg = {}

    features.update(
        {
            "multi_PER": float(adv_agg.get("PER") or adv_agg.get("PER_proxy") or 0.0),
            "multi_WS": float(
                adv_agg.get("WS") or adv_agg.get("WS_proxy_per_game") or 0.0
            ),
            "multi_TS_PCT": float(adv_agg.get("TS_PCT") or 0.0),
            "multi_USG_PCT": float(adv_agg.get("USG_PCT") or 0.0),
            "multi_season_PTS_avg": float(season_agg.get("PTS") or 0.0),
            "multi_season_count": (
                int(len(multi_season_stats))
                if isinstance(multi_season_stats, dict)
                else 0
            ),
        }
    )
    # include aggregated BPM when available
    try:
        features["multi_BPM"] = float(
            adv_agg.get("BPM")
            or adv_agg.get("BPM_48")
            or adv_agg.get("BPM_approx")
            or 0.0
        )
    except Exception:
        features["multi_BPM"] = 0.0
    # Additional advanced/team aggregated metrics (DataFrame path)
    features.update(
        {
            "multi_PIE": float(adv_agg.get("PIE") or 0.0),
            "multi_off_rating": float(adv_agg.get("OFF_RATING") or 0.0),
            "multi_def_rating": float(adv_agg.get("DEF_RATING") or 0.0),
        }
    )

    # Attempt league-level normalization (z-score) similar to dict path
    try:
        from backend.services import nba_stats_client as _nba

        season_to_use = None
        if isinstance(multi_season_stats, dict) and len(multi_season_stats) > 0:
            try:
                season_to_use = list(multi_season_stats.keys())[0]
            except Exception:
                season_to_use = None

        if season_to_use:
            league_map = _nba.fetch_league_player_advanced(season_to_use)
            if league_map:
                per_vals = []
                ts_vals = []
                for pid, stats in league_map.items():
                    try:
                        if "PER" in stats:
                            per_vals.append(float(stats["PER"]))
                    except Exception:
                        pass
                    try:
                        if "TS_PCT" in stats:
                            ts_vals.append(float(stats["TS_PCT"]))
                    except Exception:
                        pass

                import math

                def _z(v, vals):
                    try:
                        if v is None:
                            return 0.0
                        if not vals:
                            return 0.0
                        mean = float(sum(vals) / len(vals))
                        var = float(sum((x - mean) ** 2 for x in vals) / len(vals))
                        std = math.sqrt(var) if var > 0.0 else 0.0
                        return float((v - mean) / std) if std > 0.0 else 0.0
                    except Exception:
                        return 0.0

                features["multi_PER_z"] = _z(features.get("multi_PER"), per_vals)
                features["multi_TS_pct_z"] = _z(features.get("multi_TS_PCT"), ts_vals)
    except Exception:
        pass

    # --- Player-context features (DataFrame path)
    try:
        contract = player_data.get("contract") or {}
        end_year = (
            contract.get("end_year")
            or contract.get("contractEndYear")
            or player_data.get("contractEndYear")
        )
        current_year = datetime.now().year
        is_contract_year = 0
        try:
            if end_year is not None:
                if int(end_year) in (current_year, current_year + 1):
                    is_contract_year = 1
        except Exception:
            is_contract_year = 0
        features["is_contract_year"] = is_contract_year

        is_all_star = (
            1
            if (
                player_data.get("isAllStar")
                or player_data.get("allStar")
                or player_data.get("all_star")
            )
            else 0
        )
        features["is_all_star"] = is_all_star

        awards = player_data.get("awards") or []
        try:
            features["recent_awards_count"] = int(len(awards))
        except Exception:
            features["recent_awards_count"] = 0

        # trade sentiment from llm fetch result above
        try:
            features["trade_sentiment"] = float(features.get("trade_sentiment") or 0.0)
        except Exception:
            features["trade_sentiment"] = 0.0
    except Exception:
        features["is_contract_year"] = 0
        features["is_all_star"] = 0
        features["recent_awards_count"] = 0
        features["trade_sentiment"] = 0.0

    # --- Phase 3 wiring: attempt to enrich features with advanced metrics and LLM-derived features
    try:
        # Advanced metrics (PER, TS%, USG%, ORtg/DRtg) fetched when available
        from backend.services.advanced_metrics_service import (
            create_default_service as _create_adv,
        )

        adv_svc = _create_adv()
        pid = (
            player_data.get("player_id")
            or player_data.get("playerId")
            or player_data.get("playerName")
        )
        if pid:
            try:
                adv = adv_svc.fetch_advanced_metrics(str(pid))
                if adv:
                    # merge into features using safe keys
                    features["adv_PER"] = float(adv.get("PER") or 0.0)
                    features["adv_WS"] = float(adv.get("WS") or 0.0)
                    features["adv_TS_pct"] = float(adv.get("TS_pct") or 0.0)
                    features["adv_USG_pct"] = float(adv.get("USG_pct") or 0.0)
                    features["adv_ORtg"] = float(adv.get("ORtg") or 0.0)
                    features["adv_DRtg"] = float(adv.get("DRtg") or 0.0)
                    # BPM (or approximate BPM) when available
                    try:
                        features["adv_BPM"] = float(
                            adv.get("BPM")
                            or adv.get("BPM_48")
                            or adv.get("BPM_approx")
                            or 0.0
                        )
                    except Exception:
                        features["adv_BPM"] = 0.0
            except Exception:
                # non-fatal: continue if service call fails
                pass
    except Exception:
        # service module may not be present in some lightweight dev environments
        pass

    try:
        # LLM-derived qualitative features: injury sentiment, morale, motivation
        from backend.services.llm_feature_service import (
            create_default_service as _create_llm,
        )

        llm_svc = _create_llm()

        # text_fetcher: prefer prepopulated summary in player_data, fallback to empty
        def _text_fetcher(name: str) -> str:
            return player_data.get("news_summary") or player_data.get("news") or ""

        pname = (
            player_data.get("playerName")
            or player_data.get("player_name")
            or str(player_data.get("player_id") or "")
        )
        try:
            # Prefer the structured JSON path when available
            text_context = _text_fetcher(pname)
            if hasattr(llm_svc, "extract_from_text"):
                try:
                    structured = llm_svc.extract_from_text(pname, text_context)
                except Exception:
                    structured = None
                if structured:
                    # structured keys from QualitativeFeatures: news_sentiment, morale_score, motivation, trade_sentiment
                    features.update(
                        {
                            "injury_sentiment": float(
                                structured.get("news_sentiment") or 0.0
                            ),
                            "morale_score": float(
                                structured.get("morale_score") or 0.0
                            ),
                            "motivation": float(structured.get("motivation") or 0.0),
                            "trade_sentiment": float(
                                structured.get("trade_sentiment") or 0.0
                            ),
                        }
                    )
                    raise StopIteration  # skip fallback when structured succeeded

            # fallback: older fetch_news_and_extract which may use heuristics or provider text parsing
            llm_feats = llm_svc.fetch_news_and_extract(pname, "news_v1", _text_fetcher)
            if llm_feats:
                features.update(
                    {
                        "injury_sentiment": float(
                            llm_feats.get("injury_sentiment") or 0.0
                        ),
                        "morale_score": float(llm_feats.get("morale_score") or 0.0),
                        "motivation": float(llm_feats.get("motivation") or 0.0),
                        "trade_sentiment": float(
                            llm_feats.get("trade_sentiment")
                            or llm_feats.get("trade_sent")
                            or 0.0
                        ),
                    }
                )
        except StopIteration:
            # structured path succeeded; continue
            pass
        except Exception:
            pass
    except Exception:
        pass

    # opponent features (optional)
    if opponent_data:
        features["opp_def_rating"] = opponent_data.get("defensiveRating")
        features["opp_pace"] = opponent_data.get("pace")
    else:
        features["opp_def_rating"] = None
        features["opp_pace"] = None

    # Opponent-adjusted features: average vs stronger/weaker defenses and
    # historical matchup stats. This uses per-game metadata in `recentGames`
    # when available (`opponentDefRating`, `opponentTeamId`, `opponentAbbrev`).
    adv = _calculate_opponent_adjusted(recent, opponent_data)
    features.update(adv)

    # Add contextual Phase 3 features (playoff, rivalry, national TV, travel, altitude)
    try:
        _add_contextual_features(features, player_data, opponent_data)
    except Exception:
        pass

    # Phase 3: attempt to enrich features with player-tracking derived metrics.
    # This import is defensive so environments without tracking data won't fail.
    try:
        from backend.services.player_tracking_service import (
            features_for_player as _trk_features_for_player,
        )

        pname = (
            player_data.get("playerName")
            or player_data.get("player_name")
            or player_data.get("playerId")
            or player_data.get("player_id")
            or None
        )
        if pname:
            try:
                tr_feats = _trk_features_for_player(str(pname), seasons=None)
                if isinstance(tr_feats, dict):
                    for k, v in tr_feats.items():
                        try:
                            features[f"trk_{k}"] = float(v) if v is not None else 0.0
                        except Exception:
                            features[f"trk_{k}"] = 0.0
            except Exception:
                # non-fatal: tracking may not be available or may error on read
                pass
    except Exception:
        # non-fatal if module not present
        pass

    df = pd.DataFrame([features])
    # Fill missing values and ensure correct dtypes; call infer_objects to avoid
    # future downcasting behavior changes in pandas.
    df = df.fillna(0)
    try:
        # Non-fatal: infer_objects will attempt to downcast object dtypes safely.
        df = df.infer_objects(copy=False)
    except Exception:
        # If pandas version doesn't support the option or it fails, continue.
        pass

    return df


def _calculate_opponent_adjusted(
    recent_games: List[Dict], opponent_data: Optional[Dict]
) -> Dict:
    """Compute opponent-adjusted features from recent games and current opponent.

    Returns keys:
      - games_vs_current_opponent: int
      - avg_vs_current_opponent: float or None
      - avg_vs_stronger_def: float or None  (avg vs opponents with def rating <= current opponent)
      - avg_vs_similar_def: float or None   (avg vs opponents with def rating within +/-2 pts)
      - last_game_vs_current_opponent_date: str or None
      - last_game_vs_current_opponent_stat: float or None

    This function tolerates missing per-game opponentDefRating and team identifiers.
    """
    out = {
        "games_vs_current_opponent": 0,
        "avg_vs_current_opponent": None,
        "avg_vs_stronger_def": None,
        "avg_vs_similar_def": None,
        "last_game_vs_current_opponent_date": None,
        "last_game_vs_current_opponent_stat": None,
    }

    if not recent_games:
        return out

    # Gather opponent def ratings from recent games when available
    opp_ratings = [
        g.get("opponentDefRating")
        for g in recent_games
        if g.get("opponentDefRating") is not None
    ]
    opp_ratings = [float(x) for x in opp_ratings]

    # Current opponent defensive rating (if provided)
    current_opp_def = None
    current_team_id = None
    if opponent_data:
        current_opp_def = opponent_data.get("defensiveRating")
        current_team_id = (
            opponent_data.get("teamId")
            or opponent_data.get("team")
            or opponent_data.get("abbrev")
        )

    # Stats for various buckets
    vals_vs_current = []
    vals_vs_stronger = []
    vals_vs_similar = []

    for g in recent_games:
        stat = g.get("statValue")
        if stat is None:
            continue
        # match by team id or abbrev if available
        opp_id = g.get("opponentTeamId") or g.get("opponent") or g.get("opponentAbbrev")
        opp_def = g.get("opponentDefRating")

        # games vs current opponent
        if (
            current_team_id is not None
            and opp_id is not None
            and str(opp_id) == str(current_team_id)
        ):
            vals_vs_current.append(float(stat))
            # record last game info (first occurrence is most recent because recent_games are ordered newest-first)
            if out["last_game_vs_current_opponent_date"] is None:
                out["last_game_vs_current_opponent_date"] = g.get("date")
                out["last_game_vs_current_opponent_stat"] = float(stat)

        # stronger = opponent defensive rating numerically <= current opponent def (lower defensive rating => stronger defense)
        if current_opp_def is not None and opp_def is not None:
            try:
                opp_def_f = float(opp_def)
                if opp_def_f <= float(current_opp_def):
                    vals_vs_stronger.append(float(stat))
                # similar within +/- 2 rating points
                if abs(opp_def_f - float(current_opp_def)) <= 2.0:
                    vals_vs_similar.append(float(stat))
            except Exception:
                pass

    if vals_vs_current:
        out["games_vs_current_opponent"] = len(vals_vs_current)
        out["avg_vs_current_opponent"] = float(np.mean(vals_vs_current))

    if vals_vs_stronger:
        out["avg_vs_stronger_def"] = float(np.mean(vals_vs_stronger))

    if vals_vs_similar:
        out["avg_vs_similar_def"] = float(np.mean(vals_vs_similar))

    return out


# Compatibility wrapper expected by training scripts
class FeatureEngineering:
    @staticmethod
    def engineer_features(
        player_data: Dict, opponent_data: Optional[Dict] = None
    ) -> pd.DataFrame:
        """Compatibility shim: returns the same DataFrame as the module-level function."""
        return engineer_features(player_data, opponent_data)


# --- Contextual feature importance & pruning helpers (Phase 3 finalization)
CONTEXTUAL_FEATURE_KEYS = [
    "is_playoff",
    "is_national_tv",
    "is_rivalry",
    "travel_distance_km",
    "opp_altitude_m",
    "is_high_altitude_opp",
    "is_contract_year",
    "is_all_star",
    "recent_awards_count",
    "trade_sentiment",
    # LLM-derived qualitative features
    "injury_sentiment",
    "morale_score",
    "motivation",
]


def analyze_contextual_feature_importance(
    df: pd.DataFrame, target_col: str = "target", n_estimators: int = 50
) -> "pd.Series[float]":
    """Compute importance scores for known contextual features against the target.

    Uses a small RandomForestRegressor on the contextual columns present in `df`.
    Returns a pandas Series indexed by feature name sorted desc by importance.
    If there are not enough rows or no contextual features present, returns an empty Series.
    """
    try:
        from sklearn.ensemble import RandomForestRegressor
    except Exception:
        # scikit-learn not available
        return pd.Series(dtype=float)

    if target_col not in df.columns:
        return pd.Series(dtype=float)

    ctx_cols = [c for c in CONTEXTUAL_FEATURE_KEYS if c in df.columns]
    if not ctx_cols:
        return pd.Series(dtype=float)

    # require a minimal number of rows to compute importances
    if df.shape[0] < 10:
        return pd.Series(dtype=float)

    X = df[ctx_cols].select_dtypes(include=[np.number]).fillna(0)
    if X.shape[1] == 0:
        return pd.Series(dtype=float)
    y = pd.to_numeric(df[target_col], errors="coerce").fillna(0)

    try:
        model = RandomForestRegressor(n_estimators=int(n_estimators), random_state=42)
        model.fit(X, y)
        imps = pd.Series(model.feature_importances_, index=X.columns)
        imps = imps.sort_values(ascending=False)
        return imps
    except Exception:
        return pd.Series(dtype=float)


def prune_contextual_features(
    df: pd.DataFrame, target_col: str = "target", threshold: float = 0.01
) -> (pd.DataFrame, list):
    """Remove contextual features whose importance is below `threshold`.

    Returns a tuple: (pruned_df, kept_feature_list). If analysis cannot be
    performed (too few rows, sklearn missing), returns the original df and []
    for kept features.
    """
    imps = analyze_contextual_feature_importance(df, target_col=target_col)
    if imps.empty:
        return df, []

    keep = imps[imps >= float(threshold)].index.tolist()
    # Drop contextual columns that are present but not in `keep`
    to_drop = [c for c in imps.index.tolist() if c not in keep and c in df.columns]
    if to_drop:
        df = df.drop(columns=to_drop)
    return df, keep
