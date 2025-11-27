#!/usr/bin/env python3
"""
Lightweight Alembic graph validator.

Checks that the alembic directory has a single head and attempts to apply
the migrations to a disposable SQLite database to detect unresolved
down_revision errors or SQL errors that only surface during migration.

Usage:
  python backend/scripts/check_alembic_graph.py [--database-url <SQLALCHEMY_URL>]

Return codes:
  0 - OK
  1 - alembic.ini not found
  2 - multiple heads detected
  3 - upgrade failed (see output)
"""
import argparse
import os
import sys
import tempfile

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory


def main(argv=None):
    argv = argv or sys.argv[1:]
    parser = argparse.ArgumentParser(description="Validate Alembic migration graph")
    parser.add_argument(
        "--database-url",
        help="SQLAlchemy database URL to test migrations against (overrides alembic.ini)",
    )
    parser.add_argument(
        "--alembic-ini",
        default=os.path.join(os.path.dirname(__file__), "..", "alembic.ini"),
        help="Path to alembic.ini",
    )

    args = parser.parse_args(argv)

    alembic_ini = os.path.abspath(args.alembic_ini)
    if not os.path.exists(alembic_ini):
        print(f"ERROR: alembic.ini not found at {alembic_ini}")
        return 1

    cfg = Config(alembic_ini)
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    if not heads:
        print("ERROR: no migration heads found in alembic directory")
        return 2
    if len(heads) > 1:
        print("ERROR: multiple alembic heads found:", heads)
        print(
            "This indicates divergent migration branches. Run `alembic merge` to combine heads."
        )
        return 2

    # Choose a disposable sqlite file if none provided
    temp_db_file = None
    db_url = args.database_url
    if not db_url:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        temp_db_file = tmp.name
        db_url = f"sqlite:///{temp_db_file}"

    cfg.set_main_option("sqlalchemy.url", db_url)

    print(f"Alembic head: {heads[0]}")
    print(f"Testing alembic upgrade against: {db_url}")

    try:
        command.upgrade(cfg, "head")
    except Exception as exc:  # pragma: no cover - surface errors to caller
        print("ERROR: alembic upgrade failed:")
        print(exc)
        return 3
    finally:
        if temp_db_file:
            try:
                os.unlink(temp_db_file)
            except Exception:
                pass

    print("SUCCESS: migrations apply cleanly and migration graph has a single head.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
