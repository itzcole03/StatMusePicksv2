"""create player_stats hypertable and indexes

Revision ID: 0004_create_player_stats_hypertable
Revises: 0003_add_indexes
Create Date: 2025-11-11 19:40:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0004_player_stats_ht'
down_revision = '0003_add_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Only run Timescale/Postgres-specific SQL on a Postgres dialect.
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        # Non-Postgres DB (e.g., SQLite in CI/dev) - skip hypertable/index creation.
        print('Skipping Timescale hypertable/index creation: non-postgres dialect detected')
        return

    # Convert existing `player_stats` table to a TimescaleDB hypertable if the extension is available.
    # NOTE: Installing the extension in production may require DBA privileges; ensure it's enabled before running.
    try:
        # Use `created_at` as the hypertable time column (existing timestamp on player_stats).
        op.execute("SELECT create_hypertable('player_stats','created_at', if_not_exists => TRUE);")
    except Exception:
        # If create_hypertable fails (extension not present) bubble the error to the operator.
        raise

    # Create production-grade indexes concurrently to avoid locking large tables.
    # Use autocommit_block so CONCURRENTLY index creation is executed outside a transaction.
    ctx = op.get_context()
    with ctx.autocommit_block():
        op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_player_stats_player_created_at ON player_stats (player_id, created_at);")
        op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_player_stats_created_at ON player_stats (created_at);")


def downgrade() -> None:
    # Drop the indexes created above. Use CONCURRENTLY to avoid table locks.
    ctx = op.get_context()
    with ctx.autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_player_stats_player_created_at;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_player_stats_created_at;")

    # Note: We intentionally do not attempt to "undo" a hypertable conversion here. Rolling back a hypertable
    # conversion on large production tables is risky; prefer restoring from backup or using the Blue/Green strategy
    # described in the runbook (`backend/TIMESCALE_ROLLOUT.md`).
