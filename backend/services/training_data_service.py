"""Training data builder that integrates optimized NBA fetching and feature engineering.

This module provides helpers used by Phase 2 training pipelines to build
historical training datasets without leaking future information.
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional, Tuple
import logging
import pandas as pd

from backend.services import nba_service
from backend.services.feature_engineering import engineer_features

logger = logging.getLogger(__name__)


def build_training_sample(player: str, stat: str, game_date: str, season: str) -> Dict[str, Any]:
    """Build a single training sample context.

    Returns a dict containing engineered features and raw context useful for
    debugging or labeling. This function calls `get_player_context_for_training`
    which ensures season-scoped data is used (avoids leakage).
    """
    ctx = nba_service.get_player_context_for_training(player=player, stat=stat, game_date=game_date, season=season)

    # engineer features using the central shared utilities
    # Note: engineer_features expects player_data keyed like the API service.
    # We map fields appropriately.
    player_data = {
        "recentGames": ctx.get("recentGamesRaw") or [],
        "seasonAvg": ctx.get("seasonStats", {}).get("PTS") if isinstance(ctx.get("seasonStats"), dict) else None,
        "contextualFactors": {},
    }

    # opponent data may be empty for training-time feature building
    features_df = engineer_features(player_data, None)

    sample = {
        "player": player,
        "playerId": ctx.get("playerId"),
        "season": season,
        "gameDate": game_date,
        "features": features_df.iloc[0].to_dict() if not features_df.empty else {},
        "raw_context": ctx,
    }
    return sample


def build_dataset_from_specs(specs: List[Dict[str, str]]) -> Tuple[pd.DataFrame, pd.Series]:
    """Given a list of sample specs, build a training dataset.

    Each spec should be a dict with keys: `player`, `stat`, `game_date`, `season`,
    and optionally `label` (the target numeric value). If `label` is missing the
    sample will be omitted from the returned (X, y) pairs.
    """
    rows = []
    targets = []
    for s in specs:
        try:
            sample = build_training_sample(s["player"], s["stat"], s["game_date"], s["season"])
            feats = sample["features"]
            label = s.get("label")
            if label is None:
                # skip unlabeled sample
                continue
            rows.append(feats)
            targets.append(float(label))
        except Exception as e:
            logger.exception("failed to build sample for %s: %s", s, e)

    if not rows:
        return pd.DataFrame(), pd.Series(dtype=float)

    X = pd.DataFrame(rows)
    y = pd.Series(targets, name="target")
    # basic cleaning: fill NaNs with 0 and ensure numeric types
    X = X.fillna(0)
    for c in X.columns:
        try:
            X[c] = pd.to_numeric(X[c], errors="coerce").fillna(0)
        except Exception:
            pass

    return X, y
