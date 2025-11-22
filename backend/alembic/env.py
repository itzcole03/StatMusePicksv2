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
# Mark that Alembic env is running so in-repo code can detect this and
# avoid calling metadata.create_all() or performing DDL that conflicts
# with migrations during import-time.
os.environ.setdefault("ALEMBIC_RUNNING", "1")

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

        # Ensure the alembic_version.version_num column can hold longer
        # revision identifiers (some revision filenames/ids exceed 32 chars).
        # This is a safe, non-fatal guard: if the table/column doesn't exist
        # or the ALTER is unsupported it will be ignored.
        try:
            from sqlalchemy import inspect, text

            inspector = inspect(connection)
            if inspector.has_table("alembic_version"):
                # Try several ALTER forms to handle PostgreSQL and other adapters.
                # If ALTER fails (e.g., SQLite), attempt a safe SQLite-compatible
                # workaround below.
                try:
                    connection.execute(
                        text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64);")
                    )
                except Exception:
                    try:
                        # Some Postgres setups require USING cast syntax.
                        connection.execute(
                            text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64) USING version_num::VARCHAR;")
                        )
                    except Exception:
                        # As a last resort for SQLite, try the safe copy/rename pattern.
                        try:
                            dialect_name = connection.dialect.name
                            if dialect_name == "sqlite":
                                # SQLite: recreate table with wider column.
                                # This is best-effort and only runs when alembic_version exists.
                                connection.execute(
                                    text(
                                        "CREATE TABLE IF NOT EXISTS alembic_version_new (version_num VARCHAR(64) PRIMARY KEY);")
                                )
                                connection.execute(
                                    text(
                                        "INSERT OR REPLACE INTO alembic_version_new (version_num) SELECT version_num FROM alembic_version;"
                                    )
                                )
                                connection.execute(text("DROP TABLE alembic_version;"))
                                connection.execute(text("ALTER TABLE alembic_version_new RENAME TO alembic_version;"))
                        except Exception:
                            # ignore any failure here — migrations will still proceed and
                            # the underlying error will surface if this was insufficient.
                            pass
        except Exception:
            # Keep migrations resilient to any unexpected inspection errors.
            pass

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
