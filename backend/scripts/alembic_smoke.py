"""Run Alembic upgrade head against a SQLite DB to smoke-test migrations.

This script is suitable for CI smoke runs. It reads `DATABASE_URL` from
the environment; if not set it defaults to `sqlite:///./tmp_alembic_smoke.db`.
"""

import os
import sys

from alembic import command
from alembic.config import Config


def main():
    url = os.environ.get("DATABASE_URL", "sqlite:///./tmp_alembic_smoke.db")
    here = os.path.dirname(__file__)
    project_root = os.path.dirname(here)
    alembic_ini = os.path.join(project_root, "alembic.ini")

    if not os.path.exists(alembic_ini):
        print("alembic.ini not found; ensure this script is run from repo root")
        sys.exit(2)

    cfg = Config(alembic_ini)
    cfg.set_main_option("sqlalchemy.url", url)

    try:
        command.upgrade(cfg, "head")
    except Exception as e:
        print("Alembic upgrade failed:", e)
        sys.exit(3)


if __name__ == "__main__":
    main()
