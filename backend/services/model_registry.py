from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Optional

import joblib
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql as pg_dialect

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

    def _compute_hmac(self, file_path: str) -> str | None:
        key = os.environ.get("MODEL_ARTIFACT_SIGNING_KEY")
        if not key:
            return None
        try:
            import hashlib as _hashlib
            import hmac

            bkey = key.encode("utf-8")
            with open(file_path, "rb") as fh:
                data = fh.read()
            sig = hmac.new(bkey, data, _hashlib.sha256).hexdigest()
            return sig
        except Exception:
            logger.exception("Failed to compute HMAC for %s", file_path)
            return None

    def save_model(
        self,
        player_name: str,
        model,
        version: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        """Save a model artifact to disk and persist metadata to the DB.

        `version` and `notes` are optional textual fields stored in
        `model_metadata` table for traceability.
        """
        # Write a versioned artifact under per-player directory for better organization
        safe = player_name.replace(" ", "_")
        # generate a version id if not provided
        import datetime
        import uuid

        ver_id = version or datetime.datetime.utcnow().strftime("v%Y%m%dT%H%M%SZ")
        # use uuid to avoid collisions for same-version tradeoffs
        uid = uuid.uuid4().hex[:12]
        player_dir = os.path.join(self.model_dir, safe)
        version_dir = os.path.join(player_dir, "versions", f"{ver_id}_{uid}")
        os.makedirs(version_dir, exist_ok=True)
        versioned_path = os.path.join(version_dir, "model.pkl")
        joblib.dump(model, versioned_path)
        logger.info("Saved versioned model for %s to %s", player_name, versioned_path)

        # compute artifact signature if signing key present
        artifact_sig = self._compute_hmac(versioned_path)

        # Also write the legacy flat path for backward compatibility
        legacy_path = self._model_path(player_name)
        try:
            joblib.dump(model, legacy_path)
        except Exception:
            logger.debug("Failed to write flat compatibility model for %s", player_name)

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
                logger.exception(
                    "Failed to delete predict cache prefix for %s", player_name
                )

            # Best-effort: also remove keys from the in-process fallback store so
            # invalidation is visible to async readers in environments without
            # a real Redis server (useful for tests and local dev).
            try:
                prefix = f"predict:{player_name}:"
                if hasattr(cache_module, "_fallback_store"):
                    for k in list(cache_module._fallback_store.keys()):
                        if k.startswith(prefix):
                            try:
                                del cache_module._fallback_store[k]
                            except Exception:
                                pass
            except Exception:
                logger.exception(
                    "Best-effort predict prefix cleanup failed for %s", player_name
                )

            try:
                cache_module.redis_delete_prefix_sync(f"prediction:{player_name}:")
            except Exception:
                logger.exception(
                    "Failed to delete prediction cache prefix for %s", player_name
                )

            try:
                prefix = f"prediction:{player_name}:"
                if hasattr(cache_module, "_fallback_store"):
                    for k in list(cache_module._fallback_store.keys()):
                        if k.startswith(prefix):
                            try:
                                del cache_module._fallback_store[k]
                            except Exception:
                                pass
            except Exception:
                logger.exception(
                    "Best-effort prediction prefix cleanup failed for %s", player_name
                )

            try:
                cache_module.redis_delete_prefix_sync(f"player_context:{player_name}:")
            except Exception:
                logger.exception(
                    "Failed to delete player_context cache prefix for %s", player_name
                )
            try:
                prefix = f"player_context:{player_name}:"
                if hasattr(cache_module, "_fallback_store"):
                    for k in list(cache_module._fallback_store.keys()):
                        if k.startswith(prefix):
                            try:
                                del cache_module._fallback_store[k]
                            except Exception:
                                pass
            except Exception:
                logger.exception(
                    "Best-effort player_context prefix cleanup failed for %s",
                    player_name,
                )
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
                    kept = getattr(model, "_kept_contextual_features", None)
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
                    # For backward compatibility store the legacy (flat)
                    # model path in the DB so existing tests and callers
                    # that expect `*_player.pkl` continue to work.
                    path=os.path.abspath(legacy_path),
                    notes=notes,
                )
                # Attach mlflow run_id into notes for traceability when available
                run_id = None
                try:
                    import mlflow

                    run = mlflow.active_run()
                    if run is not None and getattr(run.info, "run_id", None):
                        run_id = run.info.run_id
                        try:
                            if ins_kwargs.get("notes") is None:
                                ins_kwargs["notes"] = {"mlflow_run_id": run_id}
                            else:
                                try:
                                    parsed = (
                                        json.loads(ins_kwargs["notes"])
                                        if isinstance(ins_kwargs["notes"], str)
                                        else ins_kwargs["notes"]
                                    )
                                    if isinstance(parsed, dict):
                                        parsed["mlflow_run_id"] = run_id
                                        ins_kwargs["notes"] = parsed
                                    else:
                                        ins_kwargs["notes"] = {
                                            "orig_notes": ins_kwargs["notes"],
                                            "mlflow_run_id": run_id,
                                        }
                                except Exception:
                                    ins_kwargs["notes"] = {
                                        "orig_notes": ins_kwargs["notes"],
                                        "mlflow_run_id": run_id,
                                    }
                        except Exception:
                            pass
                except Exception:
                    run_id = None
                if kept_val is not None:
                    ins_kwargs["kept_contextual_features"] = kept_val
                # include explicit feature_list column when available
                try:
                    featlist_val = getattr(model, "_feature_list", None)
                    if featlist_val is not None:
                        ins_kwargs["feature_list"] = list(featlist_val)
                except Exception:
                    pass

                try:
                    # If Postgres, use native upsert for atomicity
                    if engine.dialect.name == "postgresql":
                        try:
                            insert_stmt = pg_dialect.insert(
                                ModelMetadata.__table__
                            ).values(**ins_kwargs)
                            do_update = insert_stmt.on_conflict_do_update(
                                index_elements=["name", "version"],
                                set_=ins_kwargs,
                            )
                            conn.execute(do_update)
                        except Exception:
                            # fallback to select+insert
                            sel = ModelMetadata.__table__.select().where(
                                (ModelMetadata.__table__.c.name == player_name)
                                & (ModelMetadata.__table__.c.version == version)
                            )
                            existing = conn.execute(sel).first()
                            if existing is not None:
                                upd = (
                                    ModelMetadata.__table__.update()
                                    .where(ModelMetadata.__table__.c.id == existing.id)
                                    .values(**ins_kwargs)
                                )
                                conn.execute(upd)
                            else:
                                ins = ModelMetadata.__table__.insert().values(
                                    **ins_kwargs
                                )
                                conn.execute(ins)
                    else:
                        # Generic DB: try select then insert/update (best-effort)
                        sel = ModelMetadata.__table__.select().where(
                            (ModelMetadata.__table__.c.name == player_name)
                            & (ModelMetadata.__table__.c.version == version)
                        )
                        existing = conn.execute(sel).first()
                        if existing is not None:
                            upd = (
                                ModelMetadata.__table__.update()
                                .where(ModelMetadata.__table__.c.id == existing.id)
                                .values(**ins_kwargs)
                            )
                            conn.execute(upd)
                        else:
                            ins = ModelMetadata.__table__.insert().values(**ins_kwargs)
                            conn.execute(ins)
                except Exception:
                    # Fallback: try serializing JSON-like fields and retry insert
                    try:
                        if (
                            "kept_contextual_features" in ins_kwargs
                            and ins_kwargs["kept_contextual_features"] is not None
                        ):
                            ins_kwargs["kept_contextual_features"] = json.dumps(
                                ins_kwargs["kept_contextual_features"]
                            )
                        if (
                            "feature_list" in ins_kwargs
                            and ins_kwargs["feature_list"] is not None
                        ):
                            ins_kwargs["feature_list"] = json.dumps(
                                ins_kwargs["feature_list"]
                            )
                        ins = ModelMetadata.__table__.insert().values(**ins_kwargs)
                        conn.execute(ins)
                    except Exception:
                        logger.exception(
                            "Failed to insert or update ModelMetadata for %s",
                            player_name,
                        )
            logger.info("Inserted ModelMetadata row for %s", player_name)
        except Exception:
            logger.exception("Failed to persist ModelMetadata for %s", player_name)

        # Save a compact JSON sidecar next to the model file containing
        # additional metadata such as kept contextual features. This avoids
        # requiring a DB migration and provides an easy way to inspect
        # model-specific feature choices later.
        try:
            meta = {
                "name": player_name,
                "version": version,
                "notes": notes,
            }
            # If model object carries a kept contextual features attribute,
            # record it in the sidecar for later inspection.
            kept = None
            try:
                kept = getattr(model, "_kept_contextual_features", None)
            except Exception:
                kept = None
            if kept is not None:
                meta["kept_contextual_features"] = list(kept)
            # include canonical feature list when available
            featlist = None
            try:
                featlist = getattr(model, "_feature_list", None)
            except Exception:
                featlist = None
            if featlist is not None:
                meta["feature_list"] = list(featlist)
                # compute and include deterministic checksum for quick validation
                try:
                    _js = json.dumps(list(featlist), separators=(",", ":"))
                    checksum = hashlib.sha256(_js.encode("utf-8")).hexdigest()
                    meta["feature_list_checksum"] = checksum
                except Exception as exc:
                    logger.debug("Failed to compute feature_list checksum: %s", exc)

            # include mlflow run id in sidecar for traceability
            try:
                if run_id is not None:
                    meta["mlflow_run_id"] = run_id
                    # also merge into notes
                    try:
                        if meta.get("notes") is None:
                            meta["notes"] = {"mlflow_run_id": run_id}
                        else:
                            try:
                                parsed = (
                                    json.loads(meta["notes"])
                                    if isinstance(meta["notes"], str)
                                    else meta["notes"]
                                )
                                if isinstance(parsed, dict):
                                    parsed["mlflow_run_id"] = run_id
                                    meta["notes"] = parsed
                                else:
                                    meta["notes"] = {
                                        "orig_notes": meta["notes"],
                                        "mlflow_run_id": run_id,
                                    }
                            except Exception:
                                meta["notes"] = {
                                    "orig_notes": meta["notes"],
                                    "mlflow_run_id": run_id,
                                }
                    except Exception:
                        pass
            except Exception:
                pass

            # If feature list present and notes is a string, attempt to merge into notes for DB visibility
            try:
                import json as _json

                if featlist is not None:
                    if meta.get("notes") is None:
                        meta["notes"] = {"feature_list": list(featlist)}
                    else:
                        # try to parse existing notes if JSON-like, else attach
                        try:
                            parsed = (
                                _json.loads(meta["notes"])
                                if isinstance(meta["notes"], str)
                                else meta["notes"]
                            )
                            if isinstance(parsed, dict):
                                parsed["feature_list"] = list(featlist)
                                meta["notes"] = parsed
                            else:
                                meta["notes"] = {
                                    "orig_notes": meta["notes"],
                                    "feature_list": list(featlist),
                                }
                        except Exception:
                            meta["notes"] = {
                                "orig_notes": meta["notes"],
                                "feature_list": list(featlist),
                            }
            except Exception:
                pass

            import json

            # Ensure checksum present in sidecar (compute again to be robust)
            try:
                if "feature_list" in meta and "feature_list_checksum" not in meta:
                    _js = json.dumps(
                        list(meta.get("feature_list", [])), separators=(",", ":")
                    )
                    meta["feature_list_checksum"] = hashlib.sha256(
                        _js.encode("utf-8")
                    ).hexdigest()
            except Exception:
                pass

            # Attach artifact signature when available
            try:
                if artifact_sig is not None:
                    meta["artifact_sig"] = artifact_sig
            except Exception:
                pass

            # Write sidecar next to versioned artifact
            sidecar_versioned = os.path.splitext(versioned_path)[0] + "_metadata.json"
            with open(sidecar_versioned, "w", encoding="utf-8") as fh:
                json.dump(meta, fh, indent=2)

            # Also write legacy sidecar next to flat path for compatibility
            try:
                legacy_sidecar = os.path.splitext(legacy_path)[0] + "_metadata.json"
                with open(legacy_sidecar, "w", encoding="utf-8") as fh:
                    json.dump(meta, fh, indent=2)
            except Exception:
                logger.debug("Failed to write legacy sidecar for %s", player_name)
            logger.info("Wrote model sidecar metadata to %s", sidecar_versioned)
        except Exception:
            logger.exception(
                "Failed to write model sidecar metadata for %s", player_name
            )

    def load_model(self, player_name: str):
        # Prefer per-player versioned model if present
        safe = player_name.replace(" ", "_")
        player_dir = os.path.join(self.model_dir, safe)
        chosen_model = None
        # look for versions/*/model.pkl and pick newest by mtime
        try:
            versions_dir = os.path.join(player_dir, "versions")
            if os.path.isdir(versions_dir):
                candidate_files = []
                for root, dirs, files in os.walk(versions_dir):
                    for f in files:
                        if f == "model.pkl":
                            candidate_files.append(os.path.join(root, f))
                if candidate_files:
                    chosen_model = max(candidate_files, key=os.path.getmtime)
        except Exception:
            logger.exception("Error scanning versioned models for %s", player_name)

        # fallback to legacy flat path
        if chosen_model is None:
            legacy = self._model_path(player_name)
            if os.path.exists(legacy):
                chosen_model = legacy
            else:
                return None

        try:
            # verify signature if signing key set
            sidecar = os.path.splitext(chosen_model)[0] + "_metadata.json"
            if os.path.exists(sidecar) and os.environ.get("MODEL_ARTIFACT_SIGNING_KEY"):
                try:
                    with open(sidecar, "r", encoding="utf-8") as fh:
                        md = json.load(fh)
                    expected = md.get("artifact_sig")
                    if expected is not None:
                        actual = self._compute_hmac(chosen_model)
                        if actual is None or actual != expected:
                            raise RuntimeError(
                                "Artifact signature mismatch for %s" % player_name
                            )
                except Exception:
                    logger.exception(
                        "Artifact signature verification failed for %s", player_name
                    )
                    raise

            model = joblib.load(chosen_model)
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
            items = set()
            # prefer per-player directories
            for name in os.listdir(self.model_dir):
                p = os.path.join(self.model_dir, name)
                if os.path.isdir(p):
                    # directory names are player safe names
                    items.add(name + ".pkl")
                elif (
                    os.path.isfile(p)
                    and name.endswith(".pkl")
                    and not name.endswith("_calibrator.pkl")
                ):
                    items.add(name)
            return sorted(items)
        except Exception:
            return []

    def load_all_models(self):
        """Load all model files from disk into the in-memory cache."""
        names = []
        for fname in self.list_models():
            try:
                player = fname[:-4].replace("_", " ")
                m = self.load_model(player)
                if m is not None:
                    names.append(player)
            except Exception:
                logger.exception("Failed to preload model file %s", fname)
        return names

    def validate_feature_list(self, player_name: str, feature_list: list) -> bool:
        """Validate a provided feature_list against the saved sidecar or DB checksum.

        Returns True if checksum matches, False otherwise or if no checksum available.
        """
        # compute checksum of provided list
        try:
            _js = json.dumps(list(feature_list), separators=(",", ":"), sort_keys=True)
            provided_checksum = hashlib.sha256(_js.encode("utf-8")).hexdigest()
        except Exception:
            return False

        # try sidecar first. Prefer versioned sidecar if present
        try:
            safe = player_name.replace(" ", "_")
            player_dir = os.path.join(self.model_dir, safe)
            sidecar_paths = []
            try:
                versions_dir = os.path.join(player_dir, "versions")
                if os.path.isdir(versions_dir):
                    for root, dirs, files in os.walk(versions_dir):
                        for f in files:
                            if f == "model.pkl":
                                sidecar_paths.append(
                                    os.path.splitext(os.path.join(root, f))[0]
                                    + "_metadata.json"
                                )
            except Exception:
                pass
            # legacy sidecar
            legacy_sidecar = (
                os.path.splitext(self._model_path(player_name))[0] + "_metadata.json"
            )
            sidecar_paths.append(legacy_sidecar)

            for sidecar in sidecar_paths:
                if os.path.exists(sidecar):
                    try:
                        with open(sidecar, "r", encoding="utf-8") as fh:
                            data = json.load(fh)
                        sc = data.get("feature_list_checksum")
                        if sc is not None:
                            return sc == provided_checksum
                    except Exception:
                        continue
        except Exception:
            pass

        # fallback: try DB lookup
        try:
            from backend.models.model_metadata import ModelMetadata  # local import

            raw_db = os.environ.get("DATABASE_URL")
            sync_url = _sync_db_url(raw_db)
            engine = create_engine(sync_url, future=True)
            with engine.begin() as conn:
                sel = ModelMetadata.__table__.select().where(
                    ModelMetadata.__table__.c.name == player_name
                )
                row = conn.execute(sel).first()
                if row is not None:
                    sc = (
                        row.get("feature_list_checksum")
                        if isinstance(row, dict)
                        else getattr(row, "feature_list_checksum", None)
                    )
                    if sc is not None:
                        return sc == provided_checksum
        except Exception:
            pass

        return False

    def save_calibrator(self, player_name: str, calibrator) -> None:
        path = self._calibrator_path(player_name)
        joblib.dump(calibrator, path)
        logger.info("Saved calibrator for %s to %s", player_name, path)
        try:
            sig = self._compute_hmac(path)
            meta = {"name": player_name}
            if sig is not None:
                meta["artifact_sig"] = sig
            sidecar = os.path.splitext(path)[0] + "_calibrator_metadata.json"
            with open(sidecar, "w", encoding="utf-8") as fh:
                json.dump(meta, fh, indent=2)
        except Exception:
            logger.exception("Failed to write calibrator sidecar for %s", player_name)

    def load_calibrator(self, player_name: str):
        path = self._calibrator_path(player_name)
        if not os.path.exists(path):
            return None
        try:
            # verify signature if present
            sidecar = os.path.splitext(path)[0] + "_calibrator_metadata.json"
            if os.path.exists(sidecar) and os.environ.get("MODEL_ARTIFACT_SIGNING_KEY"):
                try:
                    with open(sidecar, "r", encoding="utf-8") as fh:
                        md = json.load(fh)
                    expected = md.get("artifact_sig")
                    if expected is not None:
                        actual = self._compute_hmac(path)
                        if actual is None or actual != expected:
                            raise RuntimeError(
                                "Calibrator artifact signature mismatch for %s"
                                % player_name
                            )
                except Exception:
                    logger.exception(
                        "Calibrator signature verification failed for %s", player_name
                    )
                    raise
            return joblib.load(path)
        except Exception:
            logger.exception("Failed to load calibrator for %s", player_name)
            return None
