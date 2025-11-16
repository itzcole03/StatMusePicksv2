"""Lightweight ML prediction service skeleton.

This module provides:
- ``PlayerModelRegistry`` (in-memory registry for dev/test)
- ``FeatureEngineering`` helpers
- ``MLPredictionService`` with a model path and a safe fallback

It is intentionally minimal so downstream code can import it without heavy
dependencies. Training, calibration and production persistence are out of
scope for this initial skeleton and will be added later following the
technical guide.
"""

from __future__ import annotations

from typing import Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import logging
import asyncio as _asyncio

import numpy as np
import pandas as pd
import joblib

logger = logging.getLogger(__name__)

try:
    from backend.services.calibration_service import CalibratorRegistry as GlobalCalibratorRegistry
except Exception:
    GlobalCalibratorRegistry = None

# Ensure a default event loop exists for test environments that call
# ``asyncio.get_event_loop().run_until_complete(...)`` without an existing loop.
try:
    _asyncio.get_event_loop()
except RuntimeError:
    _asyncio.set_event_loop(_asyncio.new_event_loop())

# Compatibility shim: ensure `asyncio.get_event_loop()` returns a loop instead
# of raising in environments (some tests call `asyncio.get_event_loop()`
# directly). We override the function at import-time so tests that call
# `asyncio.get_event_loop()` after importing this module get a usable loop.
_orig_get_event_loop = _asyncio.get_event_loop


def _get_event_loop_compat():
    try:
        loop = _orig_get_event_loop()
        # If the returned loop is closed, create and set a fresh one.
        try:
            is_closed = False
            try:
                is_closed = loop.is_closed()
            except Exception:
                # If checking raises, treat as closed to be safe
                is_closed = True
            if is_closed:
                raise RuntimeError('Event loop is closed')
        except Exception:
            new_loop = _asyncio.new_event_loop()
            try:
                _asyncio.set_event_loop(new_loop)
            except Exception:
                pass
            return new_loop
        return loop
    except Exception:
        new_loop = _asyncio.new_event_loop()
        try:
            _asyncio.set_event_loop(new_loop)
        except Exception:
            pass
        return new_loop


# Patch the real asyncio.get_event_loop so callers in other modules receive
# a live event loop even if previous tests closed the default loop. This is a
# defensive compatibility shim for the test harness and lightweight dev use.
try:
    _asyncio.get_event_loop = _get_event_loop_compat
except Exception:
    # best-effort: if assignment fails, ignore and continue
    pass


@dataclass
class SimpleModelWrapper:
    predictor: Any
    version: Optional[str] = None
    weight: float = 1.0

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self.predictor.predict(X)


class PlayerModelRegistry:
    """Simple in-memory registry for player models (dev/test use).

    Later this will be integrated with the file-backed `PlayerModelRegistry`
    already present in the repo; for now it keeps models in memory.
    """

    def __init__(self, model_dir: Optional[str] = None):
        # support multiple versions / ensemble per player: map player -> list of wrappers
        # each entry is a SimpleModelWrapper that may include a `weight` for ensemble averaging
        self._models: Dict[str, list[SimpleModelWrapper]] = {}
        self.model_dir = Path(model_dir) if model_dir else None
        # If a directory is provided, attempt to pre-load any persisted
        # models (joblib `.pkl` files). Tests write dummy models into the
        # repository `models_store` directory using the player name with
        # spaces replaced by underscores; here we reverse that.
        if self.model_dir and self.model_dir.exists():
            for p in self.model_dir.glob("*.pkl"):
                try:
                    mdl = joblib.load(p)
                    player_name = p.stem.replace("_", " ")
                    self._models[player_name] = [SimpleModelWrapper(predictor=mdl)]
                except Exception:
                    logger.exception("Failed to load persisted model %s", p)

    def save_model(self, player_name: str, model: Any, version: Optional[str] = None, persist: bool = False, weight: float = 1.0, calibrator: Optional[Any] = None) -> None:
        """Register a model for a player. If `persist` is True and a model_dir
        is configured, the model will be written to disk using joblib. The
        `version` string, if provided, will be appended to the filename.
        """
        wrapper = SimpleModelWrapper(predictor=model, version=version, weight=float(weight or 1.0))
        self._models.setdefault(player_name, []).append(wrapper)
        if persist:
            try:
                target_dir = self.model_dir or Path("backend/models_store")
                target_dir.mkdir(parents=True, exist_ok=True)
                name = player_name.replace(" ", "_")
                fname = f"{name}{('_' + version) if version else ''}.pkl"
                joblib.dump(model, target_dir / fname)
                # persist calibrator if provided
                if calibrator is not None:
                    try:
                        cal_fname = f"{name}_calibrator{('_' + version) if version else ''}.pkl"
                        joblib.dump(calibrator, target_dir / cal_fname)
                    except Exception:
                        logger.exception("Failed to persist calibrator for %s", player_name)
            except Exception:
                logger.exception("Failed to persist model for %s", player_name)

    def get_model(self, player_name: str) -> Optional[SimpleModelWrapper]:
        """Return a best-effort model for `player_name`.

        If multiple models exist, return the ensemble wrapper that averages
        predictions from all registered models (implemented via SimpleModelWrapper
        that contains a list of predictors).
        """
        lst = self._models.get(player_name) or []
        if not lst:
            return None
        if len(lst) == 1:
            return lst[0]
        # create an ensemble wrapper that averages predictions, honoring weights
        class _Ensemble:
            def __init__(self, models_with_weights):
                # models_with_weights: list of (predictor, weight)
                self.models = models_with_weights

            def predict(self, X):
                preds = []
                weights = []
                for mdl, wt in self.models:
                    p = mdl.predict(X)
                    preds.append(np.asarray(p).reshape(-1))
                    weights.append(float(wt))
                stacked = np.vstack(preds)
                arr = np.average(stacked, axis=0, weights=np.asarray(weights))
                return arr

        predictors = [(w.predictor, w.weight) for w in lst]
        return SimpleModelWrapper(predictor=_Ensemble(predictors))

    def load_model(self, player_name: str) -> Optional[SimpleModelWrapper]:
        """Attempt to load a persisted model for `player_name` from the
        configured `model_dir` or the repository default `backend/models_store`.
        Returns the loaded SimpleModelWrapper or None if not found/failed.
        """
        safe = player_name.replace(" ", "_")
        candidates = []
        if self.model_dir:
            candidates.append(Path(self.model_dir) / f"{safe}.pkl")
            # also accept joblib style filenames
            candidates.extend(sorted(Path(self.model_dir).glob(f"{safe}_v*.*")))
            candidates.extend(sorted(Path(self.model_dir).glob(f"{safe}.*")))
        # fallback to repository default
        default_dir = Path("backend/models_store")
        if default_dir.exists():
            candidates.append(default_dir / f"{safe}.pkl")
            candidates.extend(sorted(default_dir.glob(f"{safe}_v*.*")))
            candidates.extend(sorted(default_dir.glob(f"{safe}.*")))

        for p in candidates:
            try:
                if not p.exists():
                    continue
                mdl = joblib.load(p)
                wrapper = SimpleModelWrapper(predictor=mdl)
                self._models.setdefault(player_name, []).append(wrapper)
                return wrapper
            except Exception:
                logger.exception("Failed to load model from %s", p)
                continue

        return None

    def save_calibrator(self, player_name: str, calibrator: Any, version: Optional[str] = None) -> None:
        """Persist a calibrator alongside the player's models."""
        try:
            target_dir = self.model_dir or Path("backend/models_store")
            target_dir.mkdir(parents=True, exist_ok=True)
            name = player_name.replace(" ", "_")
            fname = f"{name}_calibrator{('_' + version) if version else ''}.pkl"
            joblib.dump(calibrator, target_dir / fname)
        except Exception:
            logger.exception("Failed to persist calibrator for %s", player_name)

    def load_calibrator(self, player_name: str) -> Optional[Any]:
        """Attempt to load a persisted calibrator for `player_name`.

        Returns the loaded object or None.
        """
        safe = player_name.replace(" ", "_")
        candidates = []
        if self.model_dir:
            candidates.append(Path(self.model_dir) / f"{safe}_calibrator.pkl")
            candidates.extend(sorted(Path(self.model_dir).glob(f"{safe}_calibrator_*.*")))
        default_dir = Path("backend/models_store")
        if default_dir.exists():
            candidates.append(default_dir / f"{safe}_calibrator.pkl")
            candidates.extend(sorted(default_dir.glob(f"{safe}_calibrator_*.*")))

        for p in candidates:
            try:
                if not p.exists():
                    continue
                cal = joblib.load(p)
                return cal
            except Exception:
                logger.exception("Failed to load calibrator from %s", p)
                continue

        return None


class FeatureEngineering:
    """Minimal feature engineering helper used by the service."""

    @staticmethod
    def engineer_features(player_data: Dict) -> pd.DataFrame:
        rolling = player_data.get("rollingAverages") or {}
        last5 = rolling.get("last5Games")
        last3 = rolling.get("last3Games")
        season_avg = player_data.get("seasonAvg")

        features = {
            "last3": float(last3) if last3 is not None else 0.0,
            "last5": float(last5) if last5 is not None else 0.0,
            "season_avg": float(season_avg) if season_avg is not None else 0.0,
        }

        ctx = player_data.get("contextualFactors") or {}
        features["is_home"] = 1 if ctx.get("homeAway") == "home" else 0
        features["days_rest"] = float(ctx.get("daysRest") or 0)

        return pd.DataFrame([features])


class MLPredictionService:
    """Prediction service with a model path and safe fallback.

    Usage:
        svc = MLPredictionService()
        await svc.predict(player, stat, line, player_data)
    """

    def __init__(self, registry: Optional[PlayerModelRegistry] = None, model_dir: Optional[str] = None):
        # Allow tests and callers to pass either an explicit registry or a
        # model directory path (the repo uses file-backed stores).
        if registry is not None:
            self.registry = registry
        elif model_dir is not None:
            self.registry = PlayerModelRegistry(model_dir)
        else:
            self.registry = PlayerModelRegistry()
        # Calibration scale (1.0 = no change). Lower values shrink probabilities
        # towards 0.5. This can be tuned per-player later.
        self.calibration_scale: float = 1.0
        # default calibrator type: can be 'scale' (legacy scalar), or any
        # callable object persisted per-player. If a per-player persisted
        # calibrator exists, it will be used in preference to this global
        # scalar.
        self.default_calibrator_type: str = "scale"

    async def predict(
        self,
        player_name: str,
        stat_type: str,
        line: float,
        player_data: Dict,
        opponent_data: Optional[Dict] = None,
    ) -> Dict:
        try:
            # Build features (kept for compatibility when a model is added later)
            _ = FeatureEngineering.engineer_features(player_data)

            wrapper = self.registry.get_model(player_name)
            if wrapper:
                # Use engineered features as the model input (the persisted
                # dummy model in tests expects a shaped input).
                X = FeatureEngineering.engineer_features(player_data)
                preds = wrapper.predict(X)
                raw = float(preds[0])
                over_prob = 1.0 / (1.0 + np.exp(-(raw - line)))
                # apply calibration: prefer per-player persisted calibrator
                over_prob = await self._apply_calibration(over_prob, player_name=player_name)
                recommendation = "OVER" if over_prob > 0.55 else "UNDER"
                if 0.45 <= over_prob <= 0.55:
                    recommendation = None

                return {
                    "player": player_name,
                    "stat": stat_type,
                    "line": line,
                    "predicted_value": raw,
                    "over_probability": float(over_prob),
                    "under_probability": float(max(0.0, min(1.0, 1.0 - over_prob))),
                    "recommendation": recommendation,
                    # expected_value: simple EV assuming even-money payout: prob_over - 0.5
                    "expected_value": float(round(over_prob - 0.5, 4)),
                    # confidence expressed as percentage (0-100)
                    "confidence": float(round(over_prob * 100.0, 2)),
                }

            return await self._fallback_prediction(player_name, stat_type, player_data, line)

        except Exception:
            logger.exception("Error during prediction")
            return await self._fallback_prediction(player_name, stat_type, player_data, line)

    async def _fallback_prediction(self, player_name: str, stat_type: str, player_data: Dict, line: float) -> Dict:
        rolling = player_data.get("rollingAverages") or {}
        # Prefer last5Games when available, then last3Games, then seasonAvg.
        recent_avg = None
        if rolling is not None:
            recent_avg = rolling.get("last5Games") if rolling.get("last5Games") is not None else rolling.get("last3Games")
        if recent_avg is None:
            recent_avg = player_data.get("seasonAvg")

        # Always include the request context keys so FastAPI response validation
        # (which requires `player`, `stat`, and `line`) succeeds.
        base = {"player": player_name, "stat": stat_type, "line": line}

        if recent_avg is None:
            return {
                **base,
                "predicted_value": None,
                "over_probability": 0.5,
                "under_probability": 0.5,
                "recommendation": None,
                "confidence": 0.0,
            }

        over_prob = 0.5 + (float(recent_avg) - float(line)) * 0.05
        over_prob = max(0.05, min(0.95, over_prob))
        over_prob = await self._apply_calibration(over_prob, player_name=player_name)
        recommendation = "OVER" if over_prob > 0.55 else "UNDER"
        if 0.45 <= over_prob <= 0.55:
            recommendation = None

        return {
            **base,
            "predicted_value": float(recent_avg),
            "over_probability": float(over_prob),
            "under_probability": float(max(0.0, min(1.0, 1.0 - over_prob))),
            "recommendation": recommendation,
            "expected_value": float(round(over_prob - 0.5, 4)),
            "confidence": float(round(over_prob * 100.0, 2)),
        }

    # legacy scalar calibration is handled by `_apply_calibration_scalar`.

    async def _apply_calibration(self, prob: float, player_name: Optional[str] = None) -> float:
        """Apply calibration, preferring a per-player persisted calibrator when available.

        If a calibrator object is found via the registry it should expose either
        a `transform(p: float) -> float` method or be a callable that accepts a
        single probability and returns a calibrated probability.
        """
        # Per-player calibrator takes precedence. Prefer the central CalibratorRegistry
        # (created by training) if available, then fallback to registry persisted calibrator
        # files saved alongside models (legacy behavior).
        try:
            if player_name:
                # Try central registry first (recommended):
                try:
                    if GlobalCalibratorRegistry is not None:
                        try:
                            greg = GlobalCalibratorRegistry()
                            gcal = greg.load_calibrator(player_name)
                        except Exception:
                            gcal = None
                    else:
                        gcal = None
                except Exception:
                    gcal = None

                if gcal is not None:
                    try:
                        # Our Calibrator exposes `predict` accepting array-like
                        out = gcal.predict([prob])
                        val = float(out[0]) if hasattr(out, '__iter__') else float(out)
                        val = max(0.0, min(1.0, val))
                        return val
                    except Exception:
                        logger.exception("Error applying global calibrator for %s", player_name)

                # Legacy: try registry persisted calibrator saved alongside model artifacts
                if self.registry is not None:
                    cal = None
                    try:
                        cal = self.registry.load_calibrator(player_name)
                    except Exception:
                        cal = None

                    if cal is not None:
                        # calibrator can be a callable or an object with `transform` or `predict_proba`.
                        try:
                            res = None
                            if callable(cal):
                                res = cal(prob)
                            elif hasattr(cal, "transform"):
                                # expect transform to return iterable-like
                                tmp = cal.transform([prob])
                                res = tmp[0] if hasattr(tmp, '__iter__') else tmp
                            elif hasattr(cal, "predict_proba"):
                                out = cal.predict_proba([[prob]])
                                # expect array-like [[p0, p1]]; take class 1 probability when available
                                try:
                                    res = out[0][-1]
                                except Exception:
                                    res = out

                            # Validate and coerce the result to a float. Treat NaN/Inf or
                            # uncoercible values as a signal to fall back to scalar
                            # calibration.
                            try:
                                # If iterable with single entry (e.g., [0.8]), pick it
                                if hasattr(res, '__iter__') and not isinstance(res, (str, bytes)):
                                    # try to extract a single sensible value
                                    try:
                                        candidate = list(res)[0]
                                    except Exception:
                                        candidate = None
                                else:
                                    candidate = res

                                cand_float = float(candidate) if candidate is not None else None
                                # reject NaN/Inf
                                if cand_float is None or (
                                    cand_float != cand_float or
                                    cand_float == float('inf') or
                                    cand_float == float('-inf')
                                ):
                                    raise ValueError("invalid calibrator output")

                                # clamp to [0,1]
                                cand_float = max(0.0, min(1.0, cand_float))
                                return float(cand_float)
                            except Exception:
                                # fall through to scalar fallback below
                                logger.warning("Per-player calibrator produced invalid output for %s, falling back", player_name)
                        except Exception:
                            logger.exception("Error applying per-player calibrator for %s", player_name)

            # fallback to global scalar-based calibration
            return self._apply_calibration_scalar(prob)
        except Exception:
            logger.exception("Calibration failed")
            return self._apply_calibration_scalar(prob)

    def _apply_calibration_scalar(self, prob: float) -> float:
        if self.calibration_scale == 1.0:
            return prob
        return 0.5 + (prob - 0.5) * float(self.calibration_scale)

    def set_calibration_scale(self, scale: float):
        """Set a global calibration scale (0.0-2.0). Values <1.0 shrink
        probabilities towards 0.5; values >1.0 exaggerate confidence.
        """
        try:
            s = float(scale)
            self.calibration_scale = max(0.0, min(2.0, s))
        except Exception:
            pass


__all__ = ["PlayerModelRegistry", "MLPredictionService", "FeatureEngineering"]
