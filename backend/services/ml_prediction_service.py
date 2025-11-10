"""Minimal ML prediction service scaffold.

This implements lightweight versions of:
- PlayerModelRegistry (in-memory + disk save)
- FeatureEngineering helper
- MLPredictionService.predict() which returns a sane fallback when no model

The implementation follows the technical guide but keeps runtime dependencies
and training out of the critical path so the service can be imported safely
in development without fully-trained models present.
"""
from typing import Dict, Optional
import os
import logging

import numpy as np
import pandas as pd
from .feature_engineering import engineer_features
from .model_registry import ModelRegistry

try:
    import joblib
except Exception:
    joblib = None

try:
    from sklearn.ensemble import RandomForestRegressor, VotingRegressor
    from sklearn.linear_model import ElasticNet
except Exception:
    RandomForestRegressor = None
    VotingRegressor = None
    ElasticNet = None

try:
    from xgboost import XGBRegressor
except Exception:
    XGBRegressor = None

logger = logging.getLogger(__name__)


# Use shared feature engineering utilities


class MLPredictionService:
    def __init__(self, model_dir: str = "./backend/models_store"):
        # Use the centralized ModelRegistry for persistence
        self.registry = ModelRegistry(model_dir=model_dir)

    async def predict(self, player_name: str, stat_type: str, line: float, player_data: Dict, opponent_data: Optional[Dict] = None) -> Dict:
        """Return a prediction dict. If a trained model exists, use it; otherwise use heuristic fallback."""
        try:
            features = engineer_features(player_data, opponent_data)

            # Prefer loading persisted model via ModelRegistry
            model = self.registry.load_model(player_name)
            if model is None:
                # fallback heuristic
                recent = player_data.get("recentGames") or []
                vals = [g.get("statValue") for g in recent if g.get("statValue") is not None]
                mean = float(np.mean(vals)) if vals else float(player_data.get("seasonAvg") or 0.0)
                over_prob = 0.5 + (mean - line) * 0.05
                over_prob = float(max(0.05, min(0.95, over_prob)))
                ev = self._calculate_ev(over_prob)
                rec = "OVER" if over_prob > 0.55 else ("UNDER" if over_prob < 0.45 else None)
                return {
                    "player": player_name,
                    "stat": stat_type,
                    "line": line,
                    "predicted_value": mean,
                    "over_probability": over_prob,
                    "under_probability": 1 - over_prob,
                    "recommendation": rec,
                    "expected_value": ev,
                    "confidence": abs(over_prob - 0.5) * 200,
                }

            # If a model exists, try to predict
            try:
                # Ensure features are numeric DataFrame/array acceptable to sklearn
                raw = model.predict(features)[0]
            except Exception:
                logger.exception("model prediction failed, using fallback")
                return await self.predict(player_name, stat_type, line, player_data, opponent_data)

            # simple transform to probability (sigmoid centered on line)
            over_prob = 1.0 / (1.0 + np.exp(-(raw - line)))
            over_prob = float(max(0.0, min(1.0, over_prob)))
            ev = self._calculate_ev(over_prob)
            rec = "OVER" if over_prob > 0.55 else ("UNDER" if over_prob < 0.45 else None)

            return {
                "player": player_name,
                "stat": stat_type,
                "line": line,
                "predicted_value": float(raw),
                "over_probability": over_prob,
                "under_probability": 1 - over_prob,
                "recommendation": rec,
                "expected_value": ev,
                "confidence": abs(over_prob - 0.5) * 200,
            }

        except Exception as e:
            logger.exception("prediction error: %s", e)
            return {"player": player_name, "error": str(e)}

    @staticmethod
    def _calculate_ev(over_probability: float, odds_over: int = -110, odds_under: int = -110) -> float:
        # Convert American odds to decimal
        def to_decimal(o):
            return (o / 100.0) + 1.0 if o > 0 else (100.0 / abs(o)) + 1.0

        dec_over = to_decimal(odds_over)
        dec_under = to_decimal(odds_under)
        ev_over = (over_probability * dec_over) - 1.0
        ev_under = ((1.0 - over_probability) * dec_under) - 1.0
        return float(max(ev_over, ev_under))
