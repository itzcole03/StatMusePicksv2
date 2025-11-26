"""expand alembic_version.version_num to 64 chars

Revision ID: 0008_expand_alembic_version
Revises: 0007_add_team_stats
Create Date: 2025-11-12 00:30:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0008_expand_alembic_version"
down_revision = "0007_add_team_stats"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name
    # For Postgres, alter column type directly
    if dialect == "postgresql":
        try:
            op.execute(
                "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64);"
            )
        except Exception:
            # best-effort: if it fails, skip to avoid blocking migrations
            pass
    # For SQLite, ALTER TYPE is not supported; leave as-is (SQLite stores type affinities)
    else:
        try:
            # For other dialects, attempt a generic alter_column which may be supported
            op.alter_column(
                "alembic_version",
                "version_num",
                existing_type=sa.VARCHAR(length=32),
                type_=sa.VARCHAR(length=64),
                existing_nullable=False,
            )
        except Exception:
            # If the dialect doesn't support altering the column type, ignore.
            pass


def downgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name
    # Downgrade attempts to shrink the column back to 32; do so only for Postgres
    if dialect == "postgresql":
        try:
            op.execute(
                "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(32);"
            )
        except Exception:
            pass
    else:
        try:
            op.alter_column(
                "alembic_version",
                "version_num",
                existing_type=sa.VARCHAR(length=64),
                type_=sa.VARCHAR(length=32),
                existing_nullable=False,
            )
        except Exception:
            pass
