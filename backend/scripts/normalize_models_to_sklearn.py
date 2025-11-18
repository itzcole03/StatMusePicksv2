"""Normalize existing model artifacts to sklearn-only estimators.

This script loads each model via `ModelRegistry` (the compatibility shim
ensures legacy artifacts can be unpickled), generates synthetic feature
matrices, queries the original model to obtain target values, and trains a
lightweight `RandomForestRegressor` to mimic the original. The new sklearn
model replaces the original `.pkl` file after creating a `.orig` backup.

Run with PYTHONPATH set to the repo root:
    $env:PYTHONPATH = "${PWD}"; python backend/scripts/normalize_models_to_sklearn.py
"""
from __future__ import annotations
import os
import shutil
import logging
import numpy as np

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def normalize():
    try:
        from backend.services.model_registry import ModelRegistry
    except Exception as e:
        logger.exception("Failed to import ModelRegistry: %s", e)
        return

    try:
        from sklearn.ensemble import RandomForestRegressor
    except Exception:
        logger.error("scikit-learn required. Install backend requirements first.")
        return

    mr = ModelRegistry()
    files = mr.list_models()
    logger.info("Found %d model files", len(files))

    for fname in files:
        try:
            player = fname[:-4].replace('_', ' ')
            path = os.path.join(mr.model_dir, fname)
            backup = path + '.orig'
            if os.path.exists(backup):
                logger.info("Skipping %s (already backed up)", fname)
                continue

            # Load original model (uses compatibility shim if needed)
            model = mr.load_model(player)
            if model is None:
                logger.warning("Could not load model for %s; skipping", player)
                continue

            # Try to generate synthetic X and query predictions to derive targets
            X = None
            y = None

            # If model exposes n_features_in_, use it
            n_features = getattr(model, 'n_features_in_', None)
            if n_features is None:
                n_features = 5

            # Create synthetic feature matrix
            X = np.random.RandomState(123).randn(200, int(n_features))
            try:
                y_pred = model.predict(X)
            except Exception:
                # Try smaller feature size
                X = np.random.RandomState(123).randn(100, 5)
                try:
                    y_pred = model.predict(X)
                except Exception:
                    logger.exception("Model %s not predictive; skipping normalization", player)
                    continue

            y = np.asarray(y_pred)

            # Fit a lightweight RandomForest to mimic behavior
            try:
                rf = RandomForestRegressor(n_estimators=10, random_state=42)
                rf.fit(X, y)
            except Exception:
                logger.exception("Failed to train surrogate for %s", player)
                continue

            # Backup original and persist surrogate
            logger.info("Backing up %s -> %s", path, backup)
            shutil.copy2(path, backup)
            try:
                import joblib

                joblib.dump(rf, path)
                logger.info("Wrote normalized sklearn model for %s", player)
            except Exception:
                logger.exception("Failed to write normalized model for %s", player)
                # attempt restore
                try:
                    shutil.move(backup, path)
                except Exception:
                    logger.exception("Failed to restore original for %s", player)

        except Exception:
            logger.exception("Unexpected error while normalizing %s", fname)


if __name__ == '__main__':
    normalize()
