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

from typing import Dict, Any, List, Optional
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
        return {"mean": None, "median": None, "std": None, "sample_size": 0, "trend_slope": None}

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

    return {"mean": mean, "median": median, "std": std, "sample_size": n, "trend_slope": trend_slope}


def rolling_averages(recent_games: List[Dict[str, Any]], stat_field: str = "statValue") -> Dict[str, Optional[float]]:
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
        "is_back_to_back": 1 if (player_context.get("contextualFactors", {}).get("daysRest") == 0) else 0,
    }

    # Simple imputation for missing numeric values
    for k, v in list(features.items()):
        if v is None:
            features[k] = 0.0

    return features
"""Feature engineering helpers for player predictions.

This module provides lightweight functions used by the ML service and
eventually the training pipeline. Keep functions pure and data-frame
friendly so they can be tested independently.
"""
from typing import List, Dict, Optional
import numpy as np
import pandas as pd

# Opt-in to pandas future behavior to avoid the downcasting warning during fillna
try:
    pd.set_option('future.no_silent_downcasting', True)
except Exception:
    # Older pandas versions may not provide this option; ignore failures.
    pass


def calculate_rolling_averages(recent_games: List[Dict], windows: List[int] = [3, 5, 10]) -> Dict:
    values = [g.get("statValue") for g in recent_games if g.get("statValue") is not None]
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
            slice_vals = values[:w] if len(values) >= w else values[:len(values)]
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


def engineer_features(player_data: Dict, opponent_data: Optional[Dict] = None) -> pd.DataFrame:
    recent = player_data.get("recentGames") or []
    rolling = calculate_rolling_averages(recent)

    features = {
        "recent_mean": None,
        "recent_std": None,
        "season_avg": player_data.get("seasonAvg"),
        "is_home": 1 if player_data.get("contextualFactors", {}).get("homeAway") == "home" else 0,
        "days_rest": player_data.get("contextualFactors", {}).get("daysRest") or 0,
        # explicit back-to-back indicator: 1 when days_rest == 0, else 0
        "is_back_to_back": 1 if (player_data.get("contextualFactors", {}).get("daysRest") == 0) else 0,
    }

    vals = [g.get("statValue") for g in recent if g.get("statValue") is not None]
    if vals:
        features["recent_mean"] = float(np.mean(vals))
        features["recent_std"] = float(np.std(vals))

    features.update(rolling)

    # opponent features (optional)
    if opponent_data:
        features["opp_def_rating"] = opponent_data.get("defensiveRating")
        features["opp_pace"] = opponent_data.get("pace")
    else:
        features["opp_def_rating"] = None
        features["opp_pace"] = None

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


# Compatibility wrapper expected by training scripts
class FeatureEngineering:
    @staticmethod
    def engineer_features(player_data: Dict, opponent_data: Optional[Dict] = None) -> pd.DataFrame:
        """Compatibility shim: returns the same DataFrame as the module-level function."""
        return engineer_features(player_data, opponent_data)
