from typing import Dict, List, Optional
import logging
import os
import numpy as np
import pandas as pd
import joblib

try:
    from sklearn.ensemble import RandomForestRegressor, VotingRegressor
    from sklearn.linear_model import ElasticNet
    from xgboost import XGBRegressor
    from sklearn.isotonic import IsotonicRegression
except Exception:  # Optional heavy deps for local dev; provide safe fallbacks
    RandomForestRegressor = None
    VotingRegressor = None
    ElasticNet = None
    XGBRegressor = None
    IsotonicRegression = None

logger = logging.getLogger(__name__)


class PlayerModelRegistry:
    def __init__(self, model_dir: str = None):
        self.model_dir = model_dir or os.path.join(os.path.dirname(__file__), '..', 'models_store')
        os.makedirs(self.model_dir, exist_ok=True)
        self.player_models: Dict[str, object] = {}
        self.calibrators: Dict[str, object] = {}

    def load_model(self, player_name: str) -> bool:
        path = os.path.join(self.model_dir, f"{player_name.replace(' ', '_')}.pkl")
        if os.path.exists(path):
            try:
                self.player_models[player_name] = joblib.load(path)
                # try to load calibrator too
                cal_path = path.replace('.pkl', '_calibrator.pkl')
                if os.path.exists(cal_path):
                    self.calibrators[player_name] = joblib.load(cal_path)
                return True
            except Exception as e:
                logger.exception('Failed loading model for %s: %s', player_name, e)
                return False
        return False

    def get_model(self, player_name: str):
        return self.player_models.get(player_name)

    def register_model(self, player_name: str, model):
        self.player_models[player_name] = model
        path = os.path.join(self.model_dir, f"{player_name.replace(' ', '_')}.pkl")
        try:
            joblib.dump(model, path)
        except Exception:
            logger.exception('Failed to persist model for %s', player_name)

    def register_calibrator(self, player_name: str, calibrator):
        self.calibrators[player_name] = calibrator
        path = os.path.join(self.model_dir, f"{player_name.replace(' ', '_')}_calibrator.pkl")
        try:
            joblib.dump(calibrator, path)
        except Exception:
            logger.exception('Failed to persist calibrator for %s', player_name)


class FeatureEngineering:
    @staticmethod
    def engineer_features(player_data: Dict, opponent_data: Dict) -> pd.DataFrame:
        # Delegate to the centralized, tested feature engineering utilities so
        # training and prediction pipelines share the exact same feature set
        # (including the newly added rolling stats, WMA, slope and momentum).
        try:
            from .feature_engineering import engineer_features as shared_engineer
        except Exception:
            # Fallback: construct a minimal DataFrame to preserve behavior
            features = {
                'recent_mean': 0.0,
                'recent_median': 0.0,
                'recent_std': 0.0,
                'last_3_avg': 0.0,
                'last_5_avg': 0.0,
                'last_10_avg': 0.0,
                'exponential_moving_avg': 0.0,
                'wma_3': 0.0,
                'wma_5': 0.0,
                'slope_10': 0.0,
                'momentum_vs_5_avg': 0.0,
                'season_avg': float(player_data.get('seasonAvg') or 0.0),
                'is_home': 1 if (player_data.get('contextualFactors', {}).get('homeAway') == 'home') else 0,
                'days_rest': float(player_data.get('contextualFactors', {}).get('daysRest') or 0.0),
                'is_back_to_back': 1 if player_data.get('contextualFactors', {}).get('daysRest') == 0 else 0,
                'opp_def_rating': float(opponent_data.get('defensiveRating') or 0.0) if opponent_data else 0.0,
                'opp_pace': float(opponent_data.get('pace') or 0.0) if opponent_data else 0.0,
            }
            df = pd.DataFrame([features])
            return df.fillna(0)

        return shared_engineer(player_data or {}, opponent_data or {})


class MLPredictionService:
    def __init__(self):
        self.model_registry = PlayerModelRegistry()
        self.feature_engineer = FeatureEngineering()

    async def predict(self, player_name: str, stat_type: str, line: float, player_data: Dict, opponent_data: Dict) -> Dict:
        # Engineer features
        features = self.feature_engineer.engineer_features(player_data or {}, opponent_data or {})

        # Try to load model
        model = self.model_registry.get_model(player_name)
        if model is None:
            # attempt lazy load from disk
            self.model_registry.load_model(player_name)
            model = self.model_registry.get_model(player_name)

        if model is None:
            # fallback heuristic
            recent_avg = None
            if player_data:
                recent_avg = (player_data.get('rollingAverages') or {}).get('last5Games')
                if recent_avg is None:
                    recent_avg = player_data.get('seasonAvg')
            if recent_avg is None:
                return {
                    'recommendation': None,
                    'confidence': 0,
                    'over_probability': 0.5,
                    'predicted_value': None,
                    'expected_value': 0.0,
                }
            over_prob = 0.5 + (recent_avg - line) * 0.05
            over_prob = max(0.1, min(0.9, over_prob))
            return {
                'player': player_name,
                'stat': stat_type,
                'line': line,
                'predicted_value': float(recent_avg),
                'over_probability': float(over_prob),
                'under_probability': float(1 - over_prob),
                'recommendation': 'OVER' if over_prob > 0.55 else 'UNDER',
                'expected_value': float(max((over_prob * 1.909) - 1, ((1 - over_prob) * 1.909) - 1)),
                'confidence': float(abs(over_prob - 0.5) * 200),
            }

        # Make prediction
        try:
            raw_pred = model.predict(features)[0]
        except Exception as e:
            logger.exception('Model prediction failed: %s', e)
            raw_pred = None

        if raw_pred is None:
            return {
                'player': player_name,
                'stat': stat_type,
                'line': line,
                'predicted_value': None,
                'over_probability': 0.5,
                'under_probability': 0.5,
                'recommendation': None,
                'expected_value': 0.0,
                'confidence': 0.0,
            }

        # apply calibrator if present
        calibrator = self.model_registry.calibrators.get(player_name)
        if calibrator is not None:
            try:
                calibrated = float(calibrator.predict([raw_pred])[0])
            except Exception:
                calibrated = float(raw_pred)
        else:
            calibrated = float(raw_pred)

        # transform to probability using logistic transform around the line
        over_prob = 1.0 / (1.0 + np.exp(-(calibrated - line)))
        ev = max((over_prob * 1.909) - 1, ((1 - over_prob) * 1.909) - 1)

        return {
            'player': player_name,
            'stat': stat_type,
            'line': line,
            'predicted_value': float(calibrated),
            'over_probability': float(over_prob),
            'under_probability': float(1 - over_prob),
            'recommendation': 'OVER' if over_prob > 0.55 else 'UNDER' if over_prob < 0.45 else None,
            'expected_value': float(ev),
            'confidence': float(abs(over_prob - 0.5) * 200),
        }
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
