"""Database scaffold: async SQLAlchemy engine and session factory.

This provides a simple `get_db()` dependency for FastAPI endpoints and
an `init_db()` helper to create metadata tables. The code will use
`DATABASE_URL` env var if present; otherwise it falls back to a local
SQLite file for quick local dev.
"""
import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base


_raw_db = os.environ.get("DATABASE_URL")
# If alembic.ini or other configs left a literal ${DATABASE_URL}, ignore it
if _raw_db and "${" in _raw_db:
    _raw_db = None
DATABASE_URL = _raw_db or "sqlite+aiosqlite:///./dev.db"

# Lazily-created engine and session factory. Creating an engine at import
# time can cause issues when Alembic imports this module; delay creation
# until a session or init is actually requested.
engine = None
AsyncSessionLocal = None
Base = declarative_base()


def _ensure_engine_and_session():
    """Create the async engine and sessionmaker if not already created."""
    global engine, AsyncSessionLocal
    if engine is None:
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

        engine = create_async_engine(DATABASE_URL, echo=False, future=True)
        AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    _ensure_engine_and_session()
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create database tables from SQLAlchemy metadata (if any models defined).

    Call this during dev startup or migrations (prefer Alembic for production).
    """
    _ensure_engine_and_session()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
