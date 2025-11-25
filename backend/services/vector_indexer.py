"""Background indexer to generate embeddings and persist vector mappings.

The indexer reads items to index from a JSONL file (see `INDEXER_SOURCE_FILE`
env var) and periodically calls the `LLMFeatureService.index_texts` API to
generate embeddings and store them in the configured vector store. For each
indexed item a `VectorIndex` row is persisted so the system can avoid
re-indexing the same source_id.

This module uses a synchronous SQLAlchemy engine consistent with other
ingestion helpers in `backend/services`.
"""
from __future__ import annotations

import json
import logging
import os
from typing import List, Tuple, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from backend.services.llm_feature_service import create_default_service, LLMFeatureService
from backend.models import VectorIndex

logger = logging.getLogger(__name__)


class VectorIndexer:
    def __init__(self, db_url: Optional[str] = None, source_file: Optional[str] = None, interval_seconds: int = 300):
        raw_db = db_url or os.environ.get("DATABASE_URL") or "sqlite:///./dev.db"
        # strip async drivers if present
        raw_db = raw_db.replace("+aiosqlite", "").replace("+asyncpg", "").replace("+asyncmy", "")
        self.engine = create_engine(raw_db, future=True, poolclass=NullPool)
        self.Session = sessionmaker(bind=self.engine)
        self.source_file = source_file or os.environ.get("INDEXER_SOURCE_FILE") or os.path.join(os.path.dirname(__file__), "..", "ingest_audit", "news_to_index.jsonl")
        try:
            # ensure tables exist when not running under alembic (safe no-op if tables already exist)
            from backend.db import Base

            if not os.environ.get("ALEMBIC_RUNNING"):
                Base.metadata.create_all(self.engine)
        except Exception:
            logger.exception("VectorIndexer: failed to ensure metadata.create_all")

        self.svc: LLMFeatureService = create_default_service()
        self.interval_seconds = int(interval_seconds or int(os.environ.get("INDEXER_INTERVAL_SECONDS", "300")))

    def _read_source_items(self) -> List[Tuple[str, str, dict]]:
        """Read JSONL source file and return list of (id, text, meta) tuples."""
        path = os.path.abspath(self.source_file)
        items: List[Tuple[str, str, dict]] = []
        if not os.path.exists(path):
            logger.debug("VectorIndexer: source file does not exist: %s", path)
            return items

        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        vid = obj.get("id") or obj.get("source_id") or obj.get("news_id")
                        text = obj.get("text") or obj.get("content") or ""
                        if not vid or not text:
                            continue
                        meta = obj.get("meta") or {k: v for k, v in obj.items() if k not in ("id", "text", "content", "meta")}
                        items.append((str(vid), str(text), dict(meta)))
                    except Exception:
                        logger.debug("VectorIndexer: failed to parse line in %s", path)
                        continue
        except Exception:
            logger.exception("VectorIndexer: error reading source file %s", path)
        return items

    def _already_indexed(self, session, source_id: str) -> bool:
        return session.query(VectorIndex).filter_by(source_id=source_id).first() is not None

    def run_once(self) -> int:
        """Run a single indexing pass: read items, index new ones, persist mappings.

        Returns number of newly indexed items.
        """
        items = self._read_source_items()
        if not items:
            logger.debug("VectorIndexer.run_once: no items to index")
            return 0

        indexed_count = 0
        session = self.Session()
        try:
            # Bulk-check which source_ids are already indexed to avoid
            # repeated per-item SELECTs which can cause intermittent
            # transaction behavior in some DB/driver combos.
            source_ids = [it[0] for it in items]
            try:
                existing_rows = session.query(VectorIndex.source_id).filter(VectorIndex.source_id.in_(source_ids)).all()
                existing_ids = {r[0] for r in existing_rows}
            except Exception as exc:
                msg = str(exc).lower()
                # If the failure is due to missing table, attempt to create tables
                # and retry once. This makes the indexer resilient when running
                # in test suites that may skip metadata creation earlier.
                existing_ids = set()
                try:
                    if "no such table" in msg or "no such table: vector_index" in msg:
                        from backend.db import Base

                        Base.metadata.create_all(self.engine)
                        existing_rows = session.query(VectorIndex.source_id).filter(VectorIndex.source_id.in_(source_ids)).all()
                        existing_ids = {r[0] for r in existing_rows}
                    else:
                        # Fallback: per-item check
                        for sid in source_ids:
                            try:
                                if self._already_indexed(session, sid):
                                    existing_ids.add(sid)
                            except Exception:
                                continue
                except Exception:
                    # If retry fails, fall back to per-item check as a last resort
                    existing_ids = set()
                    for sid in source_ids:
                        try:
                            if self._already_indexed(session, sid):
                                existing_ids.add(sid)
                        except Exception:
                            continue

            to_index = [it for it in items if it[0] not in existing_ids]
            if not to_index:
                logger.debug("VectorIndexer.run_once: no new items to index (found %d total)", len(items))
                return 0

            # call LLMFeatureService.index_texts which will add vectors to vector store
            ids = self.svc.index_texts(to_index)
            for vec_id in ids:
                # find original tuple
                match = next((it for it in to_index if it[0] == vec_id), None)
                if not match:
                    continue
                source_id = match[0]
                # persist mapping; use same id as vector_id for stores that accept external ids
                vi = VectorIndex(vector_id=vec_id, source_type="news", source_id=source_id, player_id=None, model=self.svc.default_model, store=os.environ.get("VECTOR_STORE") or "inmemory")
                session.add(vi)
                indexed_count += 1
            session.commit()
        except Exception:
            logger.exception("VectorIndexer.run_once: error during indexing run")
            try:
                session.rollback()
            except Exception:
                pass
        finally:
            try:
                session.close()
            except Exception:
                pass

        logger.info("VectorIndexer.run_once: indexed %d new items", indexed_count)
        return indexed_count


def run_periodic_indexer():
    """Start a simple loop-based periodic indexer. This is a lightweight
    runner used by the `backend/scripts/run_vector_indexer.py` entrypoint.
    """
    import time

    idx = VectorIndexer()
    logger.info("Starting VectorIndexer with source_file=%s interval=%s", idx.source_file, idx.interval_seconds)
    try:
        while True:
            try:
                idx.run_once()
            except Exception:
                logger.exception("Periodic indexer loop iteration failed")
            time.sleep(idx.interval_seconds)
    except KeyboardInterrupt:
        logger.info("VectorIndexer stopped by KeyboardInterrupt")
