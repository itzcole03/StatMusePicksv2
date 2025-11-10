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
