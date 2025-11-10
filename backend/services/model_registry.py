"""Player model registry: save/load per-player models and calibrators.

This registry persists model artifacts to disk and additionally records
`ModelMetadata` rows into the database so models are discoverable and
auditable. The DB insert uses a synchronous SQLAlchemy engine created from
the environment `DATABASE_URL` (async URL patterns are converted to the
corresponding sync driver when possible).
"""
from __future__ import annotations
import os
from typing import Optional
import joblib
import logging

from sqlalchemy import create_engine

logger = logging.getLogger(__name__)


def _sync_db_url(raw: Optional[str]) -> str:
    """Convert an async SQLAlchemy URL to a sync URL for simple inserts.

    Examples:
    - sqlite+aiosqlite:///./dev.db -> sqlite:///./dev.db
    - postgresql+asyncpg://...    -> postgresql://...
    If `raw` is None or doesn't contain a known async driver suffix, return
    a sensible default local sqlite URL.
    """
    if not raw:
        return "sqlite:///./dev.db"

    # Avoid propagating literal placeholders
    if "${" in raw:
        return "sqlite:///./dev.db"

    sync = raw
    # Common async driver replacements
    sync = sync.replace("+aiosqlite", "")
    sync = sync.replace("+asyncpg", "")
    sync = sync.replace("+asyncmy", "")
    return sync


class ModelRegistry:
    def __init__(self, model_dir: str = "./backend/models_store"):
        self.model_dir = os.path.abspath(model_dir)
        os.makedirs(self.model_dir, exist_ok=True)

    def _model_path(self, player_name: str) -> str:
        safe = player_name.replace(" ", "_")
        return os.path.join(self.model_dir, f"{safe}.pkl")

    def _calibrator_path(self, player_name: str) -> str:
        safe = player_name.replace(" ", "_")
        return os.path.join(self.model_dir, f"{safe}_calibrator.pkl")

    def save_model(self, player_name: str, model, version: Optional[str] = None, notes: Optional[str] = None) -> None:
        """Save a model artifact to disk and persist metadata to the DB.

        `version` and `notes` are optional textual fields stored in
        `model_metadata` table for traceability.
        """
        path = self._model_path(player_name)
        joblib.dump(model, path)
        logger.info("Saved model for %s to %s", player_name, path)

        # Attempt to persist metadata into DB. Do this with a short-lived
        # synchronous engine so this function can be called from sync code.
        try:
            from backend.models.model_metadata import ModelMetadata  # local import

            raw_db = os.environ.get("DATABASE_URL")
            sync_url = _sync_db_url(raw_db)
            engine = create_engine(sync_url, future=True)
            with engine.begin() as conn:
                ins = ModelMetadata.__table__.insert().values(
                    name=player_name,
                    version=version,
                    path=os.path.abspath(path),
                    notes=notes,
                )
                conn.execute(ins)
            logger.info("Inserted ModelMetadata row for %s", player_name)
        except Exception:
            logger.exception("Failed to persist ModelMetadata for %s", player_name)

    def load_model(self, player_name: str):
        path = self._model_path(player_name)
        if not os.path.exists(path):
            return None
        try:
            return joblib.load(path)
        except Exception:
            logger.exception("Failed to load model for %s", player_name)
            return None

    def save_calibrator(self, player_name: str, calibrator) -> None:
        path = self._calibrator_path(player_name)
        joblib.dump(calibrator, path)
        logger.info("Saved calibrator for %s to %s", player_name, path)

    def load_calibrator(self, player_name: str):
        path = self._calibrator_path(player_name)
        if not os.path.exists(path):
            return None
        try:
            return joblib.load(path)
        except Exception:
            logger.exception("Failed to load calibrator for %s", player_name)
            return None
