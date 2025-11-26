from __future__ import annotations
import os
import joblib
import logging
from typing import Optional

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
        # In-memory cache of loaded models to enable fast predictions
        # and to make startup preloading meaningful.
        self._loaded_models = {}

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

        # Cache the model in-memory so services can use it without reloading
        try:
            self._loaded_models[player_name] = model
        except Exception:
            logger.exception("Failed to cache model in-memory for %s", player_name)

        # Invalidate any prediction/player-context caches related to this player.
        try:
            from backend.services import cache as cache_module

            # FastAPI endpoint uses `predict:` prefix; keep `prediction:` as a fallback
            try:
                cache_module.redis_delete_prefix_sync(f"predict:{player_name}:")
            except Exception:
                logger.exception("Failed to delete predict cache prefix for %s", player_name)

            # Best-effort: also remove keys from the in-process fallback store so
            # invalidation is visible to async readers in environments without
            # a real Redis server (useful for tests and local dev).
            try:
                prefix = f"predict:{player_name}:"
                if hasattr(cache_module, '_fallback_store'):
                    for k in list(cache_module._fallback_store.keys()):
                        if k.startswith(prefix):
                            try:
                                del cache_module._fallback_store[k]
                            except Exception:
                                pass
            except Exception:
                logger.exception("Best-effort predict prefix cleanup failed for %s", player_name)

            try:
                cache_module.redis_delete_prefix_sync(f"prediction:{player_name}:")
            except Exception:
                logger.exception("Failed to delete prediction cache prefix for %s", player_name)

            try:
                prefix = f"prediction:{player_name}:"
                if hasattr(cache_module, '_fallback_store'):
                    for k in list(cache_module._fallback_store.keys()):
                        if k.startswith(prefix):
                            try:
                                del cache_module._fallback_store[k]
                            except Exception:
                                pass
            except Exception:
                logger.exception("Best-effort prediction prefix cleanup failed for %s", player_name)

            try:
                cache_module.redis_delete_prefix_sync(f"player_context:{player_name}:")
            except Exception:
                logger.exception("Failed to delete player_context cache prefix for %s", player_name)
            try:
                prefix = f"player_context:{player_name}:"
                if hasattr(cache_module, '_fallback_store'):
                    for k in list(cache_module._fallback_store.keys()):
                        if k.startswith(prefix):
                            try:
                                del cache_module._fallback_store[k]
                            except Exception:
                                pass
            except Exception:
                logger.exception("Best-effort player_context prefix cleanup failed for %s", player_name)
        except Exception:
            logger.exception("Cache module not available for invalidation")

        # Attempt to persist metadata into DB. Do this with a short-lived
        # synchronous engine so this function can be called from sync code.
        try:
            from backend.models.model_metadata import ModelMetadata  # local import

            raw_db = os.environ.get("DATABASE_URL")
            sync_url = _sync_db_url(raw_db)
            engine = create_engine(sync_url, future=True)
            with engine.begin() as conn:
                # If the model object carries `_kept_contextual_features`, attempt
                # to persist it into the DB JSON column. For DBs that don't
                # support native JSON, fall back to storing a JSON string.
                kept = None
                try:
                    kept = getattr(model, '_kept_contextual_features', None)
                    if kept is not None:
                        # Normalize to a plain list
                        kept_val = list(kept)
                    else:
                        kept_val = None
                except Exception:
                    kept_val = None

                ins_kwargs = dict(
                    name=player_name,
                    version=version,
                    path=os.path.abspath(path),
                    notes=notes,
                )
                if kept_val is not None:
                    ins_kwargs['kept_contextual_features'] = kept_val
                # include explicit feature_list column when available
                try:
                    featlist_val = getattr(model, '_feature_list', None)
                    if featlist_val is not None:
                        ins_kwargs['feature_list'] = list(featlist_val)
                except Exception:
                    pass
                try:
                    # Try to update existing row for same (name, version) if it exists
                    sel = ModelMetadata.__table__.select().where(
                        (ModelMetadata.__table__.c.name == player_name) & (ModelMetadata.__table__.c.version == version)
                    )
                    existing = conn.execute(sel).first()
                    if existing is not None:
                            upd = ModelMetadata.__table__.update().where(ModelMetadata.__table__.c.id == existing.id).values(**ins_kwargs)
                            conn.execute(upd)
                    else:
                        ins = ModelMetadata.__table__.insert().values(**ins_kwargs)
                        conn.execute(ins)
                except Exception:
                    # Fallback: try serializing JSON-like fields and retry insert
                    try:
                        import json as _json
                        if 'kept_contextual_features' in ins_kwargs and ins_kwargs['kept_contextual_features'] is not None:
                            ins_kwargs['kept_contextual_features'] = _json.dumps(ins_kwargs['kept_contextual_features'])
                        # attempt a simple insert as last resort
                        ins = ModelMetadata.__table__.insert().values(**ins_kwargs)
                        conn.execute(ins)
                    except Exception:
                        logger.exception("Failed to insert or update ModelMetadata for %s", player_name)
            logger.info("Inserted ModelMetadata row for %s", player_name)
        except Exception:
            logger.exception("Failed to persist ModelMetadata for %s", player_name)

        # Save a compact JSON sidecar next to the model file containing
        # additional metadata such as kept contextual features. This avoids
        # requiring a DB migration and provides an easy way to inspect
        # model-specific feature choices later.
        try:
            meta = {
                'name': player_name,
                'version': version,
                'notes': notes,
            }
            # If model object carries a kept contextual features attribute,
            # record it in the sidecar for later inspection.
            kept = None
            try:
                kept = getattr(model, '_kept_contextual_features', None)
            except Exception:
                kept = None
            if kept is not None:
                meta['kept_contextual_features'] = list(kept)
            # include canonical feature list when available
            featlist = None
            try:
                featlist = getattr(model, '_feature_list', None)
            except Exception:
                featlist = None
            if featlist is not None:
                meta['feature_list'] = list(featlist)

            # If feature list present and notes is a string, attempt to merge into notes for DB visibility
            try:
                import json as _json
                if featlist is not None:
                    if meta.get('notes') is None:
                        meta['notes'] = {'feature_list': list(featlist)}
                    else:
                        # try to parse existing notes if JSON-like, else attach
                        try:
                            parsed = _json.loads(meta['notes']) if isinstance(meta['notes'], str) else meta['notes']
                            if isinstance(parsed, dict):
                                parsed['feature_list'] = list(featlist)
                                meta['notes'] = parsed
                            else:
                                meta['notes'] = {'orig_notes': meta['notes'], 'feature_list': list(featlist)}
                        except Exception:
                            meta['notes'] = {'orig_notes': meta['notes'], 'feature_list': list(featlist)}
            except Exception:
                pass

            import json
            sidecar = os.path.splitext(path)[0] + "_metadata.json"
            with open(sidecar, 'w', encoding='utf-8') as fh:
                json.dump(meta, fh, indent=2)
            logger.info("Wrote model sidecar metadata to %s", sidecar)
        except Exception:
            logger.exception("Failed to write model sidecar metadata for %s", player_name)

    def load_model(self, player_name: str):
        path = self._model_path(player_name)
        if not os.path.exists(path):
            return None
        try:
            model = joblib.load(path)
            # cache for future quick access
            try:
                self._loaded_models[player_name] = model
            except Exception:
                logger.exception("Failed to cache loaded model for %s", player_name)
            return model
        except Exception:
            logger.exception("Failed to load model for %s", player_name)
            return None

    def get_cached_model(self, player_name: str):
        return self._loaded_models.get(player_name)

    def list_models(self):
        """Return list of model filenames (basename) found in the model_dir."""
        try:
            return [f for f in sorted(os.listdir(self.model_dir)) if f.endswith('.pkl') and not f.endswith('_calibrator.pkl')]
        except Exception:
            return []

    def load_all_models(self):
        """Load all model files from disk into the in-memory cache."""
        names = []
        for fname in self.list_models():
            try:
                player = fname[:-4].replace('_', ' ')
                m = self.load_model(player)
                if m is not None:
                    names.append(player)
            except Exception:
                logger.exception('Failed to preload model file %s', fname)
        return names

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
