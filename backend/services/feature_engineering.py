"""Feature engineering helpers for the backend.

This is a small scaffold implementing a few basic helpers mentioned in the
roadmap: recent means, rolling averages, trend slope and simple imputations.
Extend this file as the pipeline is built out.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional
import numpy as np


def recent_stats_from_games(recent_games: List[Dict[str, Any]], stat_field: str = 'statValue') -> Dict[str, Optional[float]]:
    """Compute simple recent statistics from a list of game dicts.

    Each `game` is expected to include the numeric `stat_field` (or None).
    Returns a dictionary with mean, median, std, sample_size and trend_slope.
    """
    values = [g.get(stat_field) for g in recent_games if g.get(stat_field) is not None]
    values = [float(v) for v in values]
    n = len(values)
    if n == 0:
        return {'mean': None, 'median': None, 'std': None, 'sample_size': 0, 'trend_slope': None}

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

    return {'mean': mean, 'median': median, 'std': std, 'sample_size': n, 'trend_slope': trend_slope}


def rolling_averages(recent_games: List[Dict[str, Any]], stat_field: str = 'statValue') -> Dict[str, Optional[float]]:
    vals = [g.get(stat_field) for g in recent_games if g.get(stat_field) is not None]
    vals = [float(v) for v in vals]
    def avg(slice_vals):
        return float(np.mean(slice_vals)) if len(slice_vals) > 0 else None

    return {
        'last3': avg(vals[:3]) if len(vals) >= 1 else None,
        'last5': avg(vals[:5]) if len(vals) >= 1 else None,
        'last10': avg(vals[:10]) if len(vals) >= 1 else None,
        'ema_alpha_0_3': _ema(vals, 0.3) if len(vals) >= 1 else None
    }


def _ema(values: List[float], alpha: float) -> Optional[float]:
    if not values:
        return None
    ema = values[0]
    for v in values[1:]:
        ema = alpha * v + (1 - alpha) * ema
    return float(ema)


def engineer_features(player_context: Dict[str, Any]) -> Dict[str, Any]:
    """High-level feature engineering wrapper.

    Input: a player context containing `recentGames` and `seasonAvg`.
    Output: a flat feature dict ready for model input (scaffold).
    """
    recent = player_context.get('recentGames', []) or []
    stats = recent_stats_from_games(recent)
    rolls = rolling_averages(recent)

    features = {
        'recent_mean': stats['mean'] or player_context.get('seasonAvg'),
        'recent_median': stats['median'],
        'recent_std': stats['std'] or 0.0,
        'sample_size': stats['sample_size'],
        'trend_slope': stats['trend_slope'] or 0.0,
        'last3_avg': rolls['last3'] or player_context.get('seasonAvg'),
        'last5_avg': rolls['last5'] or player_context.get('seasonAvg'),
        'last10_avg': rolls['last10'] or player_context.get('seasonAvg'),
        'ema_0_3': rolls['ema_alpha_0_3'] or player_context.get('seasonAvg'),
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


def calculate_rolling_averages(recent_games: List[Dict], windows: List[int] = [3, 5, 10]) -> Dict:
    values = [g.get("statValue") for g in recent_games if g.get("statValue") is not None]
    out = {}
    for w in windows:
        if len(values) >= w and w > 0:
            out[f"last_{w}_avg"] = float(np.mean(values[:w]))
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
    return df.fillna(0)


# Compatibility wrapper expected by training scripts
class FeatureEngineering:
    @staticmethod
    def engineer_features(player_data: Dict, opponent_data: Optional[Dict] = None) -> pd.DataFrame:
        """Compatibility shim: returns the same DataFrame as the module-level function."""
        return engineer_features(player_data, opponent_data)
