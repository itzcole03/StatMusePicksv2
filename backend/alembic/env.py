from logging.config import fileConfig
import os

from sqlalchemy import engine_from_config, pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Ensure the project's modules are importable
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import os

# Ensure sqlalchemy.url is set to a usable value. If alembic.ini references
# ${DATABASE_URL}, replace it with the environment value or fallback to sqlite.
db_url = os.environ.get("DATABASE_URL") or "sqlite+aiosqlite:///./dev.db"
main_url = config.get_main_option("sqlalchemy.url")
if main_url and "${DATABASE_URL}" in main_url:
    config.set_main_option("sqlalchemy.url", db_url)

# Ensure the env var is set so importing `backend.db` (which reads
# `os.environ['DATABASE_URL']`) produces a valid engine URL.
os.environ.setdefault("DATABASE_URL", db_url)

from backend.db import Base  # target metadata

# import models so metadata is populated
try:
    import backend.models  # noqa: F401
except Exception:
    pass

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url") or os.environ.get("DATABASE_URL")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # use a regular (sync) engine for migrations; prefer the environment
    # DATABASE_URL (set above) so we avoid unresolved ${...} placeholders.
    db_url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    sync_url = db_url
    if db_url and db_url.startswith("sqlite+aiosqlite://"):
        sync_url = db_url.replace("sqlite+aiosqlite://", "sqlite://", 1)

    from sqlalchemy import create_engine

    connectable = create_engine(sync_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
