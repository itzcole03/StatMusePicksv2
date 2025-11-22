"""Calibration service for model outputs.

Provides simple regressional calibrators (isotonic and linear) to map raw
model predictions to observed targets. Calibrators are saved/loaded via
`ModelRegistry.save_calibrator` for persistence alongside models.
"""
from __future__ import annotations
from typing import Optional
import logging
import joblib
import os
import datetime
from datetime import timezone
import json

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, mean_absolute_error
from backend.evaluation.calibration_metrics import brier_score, expected_calibration_error

logger = logging.getLogger(__name__)


class CalibrationService:
    def __init__(self, model_dir: Optional[str] = None):
        # Use ModelRegistry for persistence
        from backend.services.model_registry import ModelRegistry

        self.registry = ModelRegistry(model_dir=model_dir) if model_dir else ModelRegistry()

    def fit_calibrator(self, y_true: np.ndarray, y_pred: np.ndarray, method: str = 'isotonic'):
        """Fit a calibrator mapping y_pred -> y_true.

        method: 'isotonic' or 'linear'
        Returns the fitted calibrator object.
        """
        y_true = np.asarray(y_true).ravel()
        y_pred = np.asarray(y_pred).ravel()
        if len(y_true) != len(y_pred) or len(y_true) < 3:
            raise ValueError('Need at least 3 paired predictions/targets to fit calibrator')

        if method == 'isotonic':
            calib = IsotonicRegression(out_of_bounds='clip')
            calib.fit(y_pred, y_true)
        elif method == 'linear':
            calib = LinearRegression()
            calib.fit(y_pred.reshape(-1, 1), y_true)
        else:
            raise ValueError(f'Unknown method {method}')

        return calib

    def evaluate(self, y_true: np.ndarray, y_pred: np.ndarray) -> dict:
        y_true = np.asarray(y_true).ravel()
        y_pred = np.asarray(y_pred).ravel()
        mse = float(mean_squared_error(y_true, y_pred))
        rmse = float(np.sqrt(mse))
        mae = float(mean_absolute_error(y_true, y_pred))
        return {'mse': mse, 'rmse': rmse, 'mae': mae}

    def fit_and_save(self, player_name: str, y_true: np.ndarray, y_pred: np.ndarray, method: str = 'isotonic') -> dict:
        """Fit calibrator and persist it via ModelRegistry.save_calibrator.

        Returns a dict with `before` and `after` metrics and the stored path.
        """
        calib = self.fit_calibrator(y_true, y_pred, method=method)
        before = self.evaluate(y_true, y_pred)
        # If we have probabilistic-ish predictions (0-1), compute Brier/ECE as well
        try:
            brier_before = float(brier_score((y_true > 0).astype(float), np.asarray(y_pred)))
            ece_before = float(expected_calibration_error((y_true > 0).astype(float), np.asarray(y_pred)))
            before.update({'brier': brier_before, 'ece': ece_before})
        except Exception:
            # non-probabilistic targets: skip
            pass
        # apply calibrator
        try:
            if method == 'linear':
                y_cal = calib.predict(np.asarray(y_pred).reshape(-1, 1))
            else:
                y_cal = calib.predict(np.asarray(y_pred))
        except Exception:
            logger.exception('Failed to apply calibrator after fit')
            y_cal = y_pred

        after = self.evaluate(y_true, y_cal)
        try:
            brier_after = float(brier_score((y_true > 0).astype(float), np.asarray(y_cal)))
            ece_after = float(expected_calibration_error((y_true > 0).astype(float), np.asarray(y_cal)))
            after.update({'brier': brier_after, 'ece': ece_after})
        except Exception:
            pass

        # persist using ModelRegistry
        try:
            self.registry.save_calibrator(player_name, calib)
        except Exception:
            logger.exception('Failed to persist calibrator for %s', player_name)

        # Write a per-player calibration report (JSON) into the model store
        try:
            reports_dir = self.registry.model_dir
            reports_dir = os.path.join(reports_dir, 'calibrator_reports')
            os.makedirs(reports_dir, exist_ok=True)
            ts = datetime.datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            safe = player_name.replace(' ', '_')
            report_path = os.path.join(reports_dir, f"{safe}_calib_report_{method}_{ts}.json")
            report = {
                'player': player_name,
                'method': method,
                'created_at': ts,
                'calibrator_path': os.path.abspath(self.registry._calibrator_path(player_name)) if hasattr(self.registry, '_calibrator_path') else None,
                'before': before,
                'after': after,
            }
            with open(report_path, 'w', encoding='utf-8') as fh:
                json.dump(report, fh, indent=2, default=str)
        except Exception:
            logger.exception('Failed to write calibrator report for %s', player_name)

        # Attempt to persist calibration metrics into model_metadata table
        try:
            from backend.models.model_metadata import ModelMetadata  # local import
            from backend.services.model_registry import _sync_db_url
            from sqlalchemy import create_engine

            raw_db = os.environ.get('DATABASE_URL')
            sync_url = _sync_db_url(raw_db)
            engine = create_engine(sync_url, future=True)
            notes = json.dumps({'calibration_method': method, 'before': before, 'after': after})
            # Use calibrator path if available
            try:
                calib_path = self.registry._calibrator_path(player_name)
            except Exception:
                calib_path = None

            with engine.begin() as conn:
                # use timezone-aware UTC timestamp for versions
                timestamp = datetime.datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                ins = ModelMetadata.__table__.insert().values(
                    name=player_name,
                    version=f'calib-{method}-{timestamp}',
                    path=os.path.abspath(calib_path) if calib_path else None,
                    notes=notes,
                )
                conn.execute(ins)
        except Exception:
            logger.exception('Failed to persist ModelMetadata for calibrator %s', player_name)

        return {'player': player_name, 'method': method, 'before': before, 'after': after}

    def load_calibrator(self, player_name: str):
        return self.registry.load_calibrator(player_name)

    def calibrate(self, player_name: str, preds):
        calib = self.load_calibrator(player_name)
        if calib is None:
            raise ValueError(f'No calibrator found for {player_name}')
        try:
            import numpy as _np

            arr = _np.asarray(preds)
            # handle linear vs isotonic by shape expectations
            if hasattr(calib, 'predict'):
                if arr.ndim == 1:
                    try:
                        return calib.predict(arr)
                    except Exception:
                        return calib.predict(arr.reshape(-1, 1))
                else:
                    return calib.predict(arr)
        except Exception:
            logger.exception('Failed to apply calibrator for %s', player_name)
            raise
