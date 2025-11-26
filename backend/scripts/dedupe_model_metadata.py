"""
Simple dedupe utility for `model_metadata` table.

Usage:
  python dedupe_model_metadata.py --database-url <DATABASE_URL> [--apply] [--backup-file out.csv]

If `--apply` is not provided the script will only print duplicates (dry-run).
When `--apply` is used, duplicates are removed keeping the latest `id` per (name, version).
A CSV backup of removed rows can be written with `--backup-file`.
"""

import argparse
import csv
import sys

from sqlalchemy import create_engine, inspect, text


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--database-url", required=False, help="DATABASE_URL (falls back to env)"
    )
    p.add_argument("--apply", action="store_true", help="Apply deletions")
    p.add_argument(
        "--backup-file", required=False, help="CSV file to write deleted rows"
    )
    args = p.parse_args()

    db = args.database_url or __import__("os").environ.get("DATABASE_URL")
    if not db:
        print("DATABASE_URL required (env or --database-url)")
        sys.exit(2)

    engine = create_engine(db)
    insp = inspect(engine)
    if "model_metadata" not in insp.get_table_names():
        print("model_metadata table not found")
        sys.exit(2)

    with engine.begin() as conn:
        # find duplicates by name+version
        q = text(
            """
        SELECT name, version, array_agg(id ORDER BY created_at DESC) as ids
        FROM model_metadata
        GROUP BY name, version
        HAVING count(*) > 1
        """
        )
        res = conn.execute(q).mappings().all()
        to_delete = []
        for row in res:
            ids = row["ids"]
            # keep the first (latest), delete the rest
            ids[0]
            del_ids = ids[1:]
            for did in del_ids:
                to_delete.append(
                    {"name": row["name"], "version": row["version"], "id": did}
                )

        if not to_delete:
            print("No duplicates found")
            return

        print(f"Found {len(to_delete)} duplicate rows to remove (dry-run).")
        if args.backup_file:
            with open(args.backup_file, "w", newline="", encoding="utf8") as fh:
                writer = csv.DictWriter(fh, fieldnames=["id", "name", "version"])
                writer.writeheader()
                for d in to_delete:
                    writer.writerow(d)
            print("Wrote backup to", args.backup_file)

        if args.apply:
            ids = [d["id"] for d in to_delete]
            chunk = 100
            for i in range(0, len(ids), chunk):
                ch = ids[i : i + chunk]
                del_q = text("DELETE FROM model_metadata WHERE id = ANY(:ids)")
                conn.execute(del_q, {"ids": ch})
            print("Deleted duplicates:", len(ids))
        else:
            print("Run with --apply to delete these rows")


if __name__ == "__main__":
    main()
"""Utility to find and optionally deduplicate `model_metadata` rows by (name, version).

Usage:
    python backend/scripts/dedupe_model_metadata.py --db-url <DATABASE_URL> [--apply] [--backup csv_path]

By default the script runs as dry-run and prints duplicate groups. Pass `--apply` to delete duplicates
keeping the newest `created_at` row per (name, version). A CSV backup of deleted rows can be written
with `--backup`.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime

from sqlalchemy import MetaData, create_engine, desc, func, select


def _sync_db_url(raw: str | None) -> str:
    if not raw:
        return "sqlite:///./dev.db"
    if "${" in raw:
        return "sqlite:///./dev.db"
    sync = raw
    sync = sync.replace("+aiosqlite", "")
    sync = sync.replace("+asyncpg", "")
    sync = sync.replace("+asyncmy", "")
    return sync


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--db-url",
        help="Database URL (sync or async); if omitted uses $DATABASE_URL or sqlite dev.db",
    )
    p.add_argument(
        "--apply", action="store_true", help="Apply deletions (default: dry-run)"
    )
    p.add_argument("--backup", help="Path to CSV backup file for deleted rows")
    args = p.parse_args()

    raw = args.db_url or os.environ.get("DATABASE_URL")
    sync_url = _sync_db_url(raw)

    engine = create_engine(sync_url, future=True)
    meta = MetaData()
    meta.reflect(bind=engine, only=["model_metadata"])
    if "model_metadata" not in meta.tables:
        print("No model_metadata table found in DB:", sync_url)
        sys.exit(1)
    t = meta.tables["model_metadata"]

    with engine.begin() as conn:
        # find duplicates
        dup_q = (
            select(t.c.name, t.c.version, func.count())
            .group_by(t.c.name, t.c.version)
            .having(func.count() > 1)
        )
        res = conn.execute(dup_q).all()
        if not res:
            print("No duplicate (name, version) groups found.")
            return

        print(f"Found {len(res)} duplicate groups. Dry-run={not args.apply}")
        deletions = []
        for name, version, cnt in res:
            print(f"Group: name={name!r}, version={version!r} count={cnt}")
            sel = (
                select(t)
                .where((t.c.name == name) & (t.c.version == version))
                .order_by(desc(t.c.created_at))
            )
            rows = conn.execute(sel).all()
            # Keep first (newest), delete rest
            rows[0]
            to_delete = rows[1:]
            for r in to_delete:
                row_map = dict(r._mapping)
                deletions.append(row_map)
                print(
                    f"  Would delete id={row_map.get('id')} path={row_map.get('path')}"
                )

        if not args.apply:
            print("\nDry-run complete. Rerun with --apply to delete duplicates.")
            return

        # backup if requested
        if args.backup and deletions:
            bk = args.backup
            with open(bk, "w", newline="", encoding="utf8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(sorted(deletions[0].keys())))
                w.writeheader()
                for d in deletions:
                    w.writerow(
                        {
                            k: (v.isoformat() if isinstance(v, datetime) else v)
                            for k, v in d.items()
                        }
                    )
            print(f"Wrote backup of {len(deletions)} deleted rows to {bk}")

        # perform deletions
        for d in deletions:
            del_q = t.delete().where(t.c.id == d.get("id"))
            conn.execute(del_q)
            print(f"Deleted id={d.get('id')}")

        print("Deletion applied.")


if __name__ == "__main__":
    main()
