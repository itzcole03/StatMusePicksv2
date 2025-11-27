"""Backfill `kept_contextual_features` into `model_metadata` from model sidecars.

Scans `backend/models_store` for JSON sidecars and nested `metadata.json` files.
For each file that contains `kept_contextual_features`, update the DB row
matching `name` and `version` (or `version_id`) if the DB column is empty.

Idempotent: skips rows that already have a non-null value.
"""

import json
import os
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT / "backend" / "models_store"
DB_URL = os.environ.get("DATABASE_URL", "sqlite:///./dev.db")


def find_metadata_files(base: Path):
    for p in base.rglob("*.json"):
        name = p.name.lower()
        if (
            name.endswith("_metadata.json")
            or name == "metadata.json"
            or "metadata" in name
        ):
            yield p


def extract_kept_from_json(p: Path):
    try:
        j = json.load(open(p, "r", encoding="utf-8"))
    except Exception:
        return None

    # ModelRegistry sidecar format
    if "kept_contextual_features" in j:
        name = j.get("name")
        version = j.get("version")
        return name, version, j.get("kept_contextual_features")

    # Nested metadata.json format used under versions/<id>/metadata.json
    # Example: {"name": "LeBron James", "version_id": "...", "metadata": {...} }
    if "name" in j and "version_id" in j:
        meta = j.get("metadata", {}) or {}
        kept = meta.get("kept_contextual_features") or meta.get("kept_features")
        return j.get("name"), j.get("version_id"), kept

    # Fallback: any top-level key
    if (
        "metadata" in j
        and isinstance(j["metadata"], dict)
        and "kept_contextual_features" in j["metadata"]
    ):
        # try to infer name/version
        name = j.get("name") or j["metadata"].get("name")
        version = j.get("version") or j["metadata"].get("version")
        return name, version, j["metadata"].get("kept_contextual_features")

    return None


def backfill():
    eng = create_engine(DB_URL, future=True)
    files = list(find_metadata_files(MODELS_DIR))
    updated = 0
    scanned = 0
    for f in files:
        scanned += 1
        rec = extract_kept_from_json(f)
        if not rec:
            continue
        name, version, kept = rec
        if not name or kept is None:
            continue

        # Normalize kept to JSON string for sqlite/text fallback
        try:
            kept_json = json.dumps(list(kept))
        except Exception:
            continue

        # Build update; only update rows where kept_contextual_features is NULL or empty
        stmt = text(
            """
            UPDATE model_metadata
            SET kept_contextual_features = :kept
            WHERE name = :name
            AND (version = :version OR :version IS NULL)
            AND (kept_contextual_features IS NULL OR kept_contextual_features = '')
            """
        )
        params = {"kept": kept_json, "name": name, "version": version}
        with eng.begin() as conn:
            res = conn.execute(stmt, params)
            if res.rowcount and res.rowcount > 0:
                updated += res.rowcount
                print(
                    f"Updated {res.rowcount} rows for {name} version={version} from {f}"
                )

    print(f"Scanned {scanned} files, updated {updated} rows")


if __name__ == "__main__":
    backfill()
