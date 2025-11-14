"""Legacy PlayerModelRegistry - file-backed registry used by training scripts.

This module provides `PlayerModelRegistry` with a simple `save_model`/`load_model`
API that stores joblib artifacts under `store_dir` and maintains an `index.json`.
It is intentionally simple for local dev and CI. Newer lightweight registries live
in `backend.services.simple_model_registry` for per-version artifact organization.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import joblib

# Adapter to register saved legacy artifacts with the per-version registry when available
try:
    from .simple_model_registry import ModelRegistry as PerVersionRegistry
except Exception:  # pragma: no cover - optional adapter import
    PerVersionRegistry = None


@dataclass
class ModelMetadata:
    player_name: str
    version: str
    model_path: str
    created_at: str
    model_type: Optional[str] = None
    notes: Optional[str] = None
    metrics: Optional[Dict] = None
    hyperparameters: Optional[Dict] = None
    feature_columns: Optional[List[str]] = None
    feature_importances: Optional[Dict[str, float]] = None
    dataset_version: Optional[str] = None


class PlayerModelRegistry:
    """A small file-backed registry for player models.

    Example usage:
        reg = PlayerModelRegistry("backend/models_store")
        version = reg.save_model("LeBron James", model_obj, metadata={...})
        reg.load_model("LeBron James", version=version)
    """

    INDEX_NAME = "index.json"

    def __init__(self, store_dir: str = "backend/models_store", model_dir: Optional[str] = None, **_kwargs):
        # Backwards-compatible: accept `model_dir` kw used by older code
        if model_dir:
            store_dir = model_dir
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        # Backwards-compatible attribute expected by some tests/consumers
        self.model_dir = str(self.store_dir)
        self.index_path = self.store_dir / self.INDEX_NAME
        self._in_memory: Dict[str, object] = {}
        # load or init index
        if self.index_path.exists():
            try:
                with open(self.index_path, "r", encoding="utf-8") as f:
                    self._index = json.load(f)
            except Exception:
                self._index = {}
        else:
            self._index = {}

    def _write_index(self) -> None:
        tmp = self.index_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2)
        tmp.replace(self.index_path)

    def _safe_name(self, player_name: str) -> str:
        return player_name.replace(" ", "_")

    def _make_version(self, player_name: str) -> str:
        ts = datetime.utcnow().isoformat(timespec="seconds")
        base = f"{player_name}-{ts}-{time.time()}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]

    def save_model(self, player_name: str, model: object, version: Optional[str] = None, metadata: Optional[Dict] = None, notes: Optional[str] = None) -> str:
        """Save a model and append metadata to index. Returns chosen version id.

        `metadata` may include `model_type`, `notes`, and `metrics`.
        If `version` is None, a deterministic time-based sha1 prefix is generated.
        """
        if version is None:
            version = self._make_version(player_name)
        # Support callers that pass `notes` as a top-level kwarg (legacy scripts)
        if metadata is None:
            metadata = {}
        if notes is not None:
            metadata.setdefault("notes", notes)
        safe = self._safe_name(player_name)
        fname = f"{safe}_v{version}.joblib"
        path = self.store_dir / fname
        joblib.dump(model, path)

        # Also write a legacy `{safe}.pkl` artifact for tests and older consumers
        try:
            legacy_path = self.store_dir / f"{safe}.pkl"
            try:
                # Try writing a joblib-dump into the legacy path as well
                joblib.dump(model, legacy_path)
            except Exception:
                # Fallback: copy bytes from the joblib file if direct dump fails
                try:
                    with open(path, "rb") as r, open(legacy_path, "wb") as w:
                        w.write(r.read())
                except Exception:
                    pass
        except Exception:
            legacy_path = None

        created_at = datetime.utcnow().isoformat()
        meta = ModelMetadata(
            player_name=player_name,
            version=version,
            model_path=str(path),
            created_at=created_at,
            model_type=(metadata.get("model_type") if metadata else None),
            notes=(metadata.get("notes") if metadata else None),
            metrics=(metadata.get("metrics") if metadata else None),
            hyperparameters=(metadata.get("hyperparameters") if metadata else None),
            feature_columns=(metadata.get("feature_columns") if metadata else None),
            feature_importances=(metadata.get("feature_importances") if metadata else None),
            dataset_version=(metadata.get("dataset_version") if metadata else None),
        )

        # append to index
        entries: List[Dict] = self._index.get(safe, [])
        entries.append(asdict(meta))
        self._index[safe] = entries
        self._write_index()

        # cache in memory for quick load without disk
        self._in_memory[player_name] = model
        # Invalidate cached predictions/player contexts for this player (best-effort)
        try:
            from backend.services import cache as cache_module

            try:
                cache_module.redis_delete_prefix_sync(f"predict:{player_name}:")
            except Exception:
                pass
            try:
                cache_module.redis_delete_prefix_sync(f"player_context:{player_name}:")
            except Exception:
                pass
        except Exception:
            # optional cache module may not be available in some test harnesses
            pass

        # Best-effort: persist metadata into DB table `model_metadata` when DATABASE_URL present
        try:
            import os
            from sqlalchemy import create_engine, text

            raw_db = os.environ.get("DATABASE_URL")
            if raw_db:
                sync_url = raw_db
                if raw_db.startswith("postgresql+asyncpg://"):
                    sync_url = raw_db.replace("+asyncpg", "")
                if raw_db.startswith("sqlite+aiosqlite://"):
                    sync_url = raw_db.replace("+aiosqlite", "")

                engine = create_engine(sync_url, future=True)
                try:
                    with engine.begin() as conn:
                            # Prefer legacy .pkl path when available (older consumers/tests expect this)
                            insert_path = str(legacy_path) if ("legacy_path" in locals() and legacy_path and legacy_path.exists()) else str(path)
                            conn.execute(
                                text(
                                    "INSERT INTO model_metadata (name, version, path, notes, created_at) VALUES (:name, :version, :path, :notes, :created_at)"
                                ),
                                {
                                    "name": player_name,
                                    "version": version,
                                    "path": insert_path,
                                    "notes": (metadata.get("notes") if isinstance(metadata, dict) else None),
                                    "created_at": created_at,
                                },
                            )
                except Exception:
                    # best-effort: do not fail save if DB insert fails
                    pass
        except Exception:
            pass
        except Exception:
            # optional cache module may not be available in some test harnesses
            pass
        # Best-effort additional cleanup of in-process fallback store used by cache
        try:
            from backend.services import cache as cache_module
            try:
                # if the in-memory fallback exists, remove matching keys directly
                store = getattr(cache_module, "_fallback_store", None)
                if isinstance(store, dict):
                    preds = [k for k in list(store.keys()) if k.startswith(f"predict:{player_name}:")]
                    for k in preds:
                        try:
                            del store[k]
                        except Exception:
                            pass
                    ctxs = [k for k in list(store.keys()) if k.startswith(f"player_context:{player_name}:")]
                    for k in ctxs:
                        try:
                            del store[k]
                        except Exception:
                            pass
            except Exception:
                pass
        except Exception:
            pass
        # Attempt to register the saved artifact with the per-version registry
        try:
            if PerVersionRegistry is not None:
                    per_reg = PerVersionRegistry()
                    # build a lightweight metadata payload
                    payload = {}
                    if meta.model_type:
                        payload["model_type"] = meta.model_type
                    if meta.notes:
                        payload["notes"] = meta.notes
                    if meta.metrics:
                        payload["metrics"] = meta.metrics
                    if meta.hyperparameters:
                        payload["hyperparameters"] = meta.hyperparameters
                    if meta.dataset_version:
                        payload["dataset_version"] = meta.dataset_version
                    # schema marker for future migrations
                    payload["schema_version"] = 1

                    # register using the safe name to avoid filesystem issues with spaces
                    try:
                        per_reg.register_model(safe, artifact_src=path, metadata=payload)
                    except Exception:
                        # best-effort: do not fail save if registry registration fails
                        pass
        except Exception:
            # swallow any unexpected errors from the adapter
            pass

        return version


    def list_models(self) -> Dict[str, List[Dict]]:
        """Return the raw index mapping of player_safe -> list[metadata]."""
        return self._index.copy()

    def list_versions(self, player_name: str) -> List[str]:
        safe = self._safe_name(player_name)
        return [e["version"] for e in self._index.get(safe, [])]

    def get_metadata(self, player_name: str, version: Optional[str] = None) -> Optional[ModelMetadata]:
        safe = self._safe_name(player_name)
        entries = self._index.get(safe, [])
        if not entries:
            return None
        if version is None:
            entry = entries[-1]
        else:
            matches = [e for e in entries if e.get("version") == version]
            entry = matches[0] if matches else None
        return ModelMetadata(**entry) if entry else None

    def load_model(self, player_name: str, version: Optional[str] = None) -> Optional[object]:
        # in-memory quick path
        if player_name in self._in_memory and version is None:
            return self._in_memory[player_name]

        safe = self._safe_name(player_name)
        entries = self._index.get(safe, [])
        if not entries:
            # try legacy `{safe}.pkl` artifact
            legacy = self.store_dir / f"{safe}.pkl"
            if legacy.exists():
                try:
                    m = joblib.load(legacy)
                    self._in_memory[player_name] = m
                    return m
                except Exception:
                    return None
            return None
        if version is None:
            path = Path(entries[-1]["model_path"])
        else:
            matches = [e for e in entries if e.get("version") == version]
            if not matches:
                return None
            path = Path(matches[0]["model_path"])

        if not path.exists():
            # Backwards-compat: try legacy `{safe}.pkl` artifact
            legacy = self.store_dir / f"{safe}.pkl"
            if legacy.exists():
                try:
                    m = joblib.load(legacy)
                    self._in_memory[player_name] = m
                    return m
                except Exception:
                    return None
            return None
        model = joblib.load(path)
        # cache
        self._in_memory[player_name] = model
        return model

    def delete_model(self, player_name: str, version: Optional[str] = None) -> bool:
        """Delete a model artifact and remove its metadata entry. Returns True if deleted."""
        safe = self._safe_name(player_name)
        entries = self._index.get(safe, [])
        if not entries:
            return False
        if version is None:
            entry = entries.pop()  # remove latest
        else:
            idx = next((i for i, e in enumerate(entries) if e.get("version") == version), None)
            if idx is None:
                return False
            entry = entries.pop(idx)

        # remove file
        try:
            p = Path(entry["model_path"])
            if p.exists():
                p.unlink()
        except Exception:
            pass

        # update index and on-disk
        if entries:
            self._index[safe] = entries
        else:
            self._index.pop(safe, None)
        self._write_index()
        # evict cache
        self._in_memory.pop(player_name, None)
        return True

    def promote_model(self, player_name: str, version: Optional[str] = None, promoted_by: Optional[str] = None, notes: Optional[str] = None, write_legacy_pkl: bool = False) -> Optional[Dict]:
        """Mark a model version as promoted (production).

        Adds promotion metadata to the selected index entry and optionally writes
        a legacy `{player_safe}.pkl` artifact for older consumers.

        Returns the updated metadata dict, or None if the player/version not found.
        """
        safe = self._safe_name(player_name)
        entries: List[Dict] = self._index.get(safe, [])
        if not entries:
            return None

        if version is None:
            idx = len(entries) - 1
        else:
            idx = next((i for i, e in enumerate(entries) if e.get("version") == version), None)
            if idx is None:
                return None

        entry = entries[idx]
        promoted_at = datetime.utcnow().isoformat()
        # attach promotion fields
        entry["promoted"] = True
        entry["promoted_at"] = promoted_at
        entry["promoted_by"] = promoted_by
        entry["promotion_notes"] = notes

        # persist index
        self._index[safe] = entries
        self._write_index()

        # Optionally write legacy .pkl for older consumers
        if write_legacy_pkl:
            try:
                model_path = Path(entry.get("model_path"))
                if model_path.exists():
                    legacy_path = self.store_dir / f"{safe}.pkl"
                    try:
                        m = joblib.load(model_path)
                        joblib.dump(m, legacy_path)
                    except Exception:
                        # best-effort: copy bytes if joblib load/dump fail
                        try:
                            with open(model_path, "rb") as r, open(legacy_path, "wb") as w:
                                w.write(r.read())
                        except Exception:
                            pass
            except Exception:
                pass

        # evict in-memory cache so next load picks promoted artifact when relevant
        self._in_memory.pop(player_name, None)
        # Best-effort: persist promotion event into DB table `model_promotions` if DATABASE_URL present
        try:
            import os
            from sqlalchemy import create_engine, text

            raw_db = os.environ.get("DATABASE_URL")
            if raw_db:
                # convert async drivers to sync equivalents when possible
                sync_url = raw_db
                if raw_db.startswith("postgresql+asyncpg://"):
                    sync_url = raw_db.replace("+asyncpg", "")
                if raw_db.startswith("sqlite+aiosqlite://"):
                    sync_url = raw_db.replace("+aiosqlite", "")

                engine = create_engine(sync_url, future=True)
                promoted_at_dt = datetime.utcnow()
                try:
                    with engine.begin() as conn:
                        conn.execute(
                            text(
                                "INSERT INTO model_promotions (player_name, version, promoted_by, promoted_at, notes) VALUES (:player, :version, :promoted_by, :promoted_at, :notes)"
                            ),
                            {
                                "player": player_name,
                                "version": version,
                                "promoted_by": promoted_by,
                                "promoted_at": promoted_at_dt,
                                "notes": notes,
                            },
                        )
                except Exception:
                    # don't fail promotion if DB insert fails
                    pass
        except Exception:
            pass

        return entry


# Also expose the legacy class for callers that expect it
LegacyModelRegistry = PlayerModelRegistry
ModelRegistry = PlayerModelRegistry