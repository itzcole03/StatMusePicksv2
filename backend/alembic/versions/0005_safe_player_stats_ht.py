"""safe convert player_stats to hypertable with guard

Revision ID: 0005_safe_player_stats_ht
Revises: 0004_player_stats_ht
Create Date: 2025-11-11 20:00:00.000000
"""

import os

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0005_safe_player_stats_ht"
down_revision = "0004_player_stats_ht"
branch_labels = None
depends_on = None


def _timescale_extension_present(conn) -> bool:
    try:
        r = conn.execute(
            sa.text("SELECT 1 FROM pg_extension WHERE extname='timescaledb' LIMIT 1;")
        )
        return r.fetchone() is not None
    except Exception:
        return False


def upgrade() -> None:
    """
    Production-safe conversion to Timescale hypertable.

    Behavior:
    - If Timescale extension is not installed, migration is a no-op.
    - If env var `FORCE_PLAYER_STATS_HT=1` is set, conversion proceeds regardless of table size.
    - Otherwise, we inspect row count and only proceed if <= threshold (default 1_000_000).
    - Index creation is executed CONCURRENTLY inside an autocommit block.
    """
    ctx = op.get_context()
    conn = op.get_bind()

    # Skip Postgres/Timescale-specific work when running on non-Postgres dialects (e.g., SQLite in CI/dev).
    if conn.dialect.name != "postgresql":
        print("Skipping Timescale hypertable conversion: non-postgres dialect detected")
        return

    if not _timescale_extension_present(conn):
        # Not an error for non-Timescale environments; skip conversion.
        print(
            "Timescale extension not found; skipping hypertable conversion for player_stats"
        )
        return

    force_flag = os.getenv("FORCE_PLAYER_STATS_HT", "0")
    threshold = int(os.getenv("PLAYER_STATS_HT_ROW_THRESHOLD", "1000000"))

    if force_flag != "1":
        try:
            cnt_res = conn.execute(sa.text("SELECT count(*) FROM player_stats;"))
            row_count = cnt_res.scalar()
        except Exception:
            # If we cannot read the table (missing), skip silently so migrations can run in CI/dev.
            print(
                "player_stats table not found or unreadable; skipping hypertable conversion"
            )
            return

        if row_count is None:
            print("Could not determine row count; skipping hypertable conversion")
            return

        if row_count > threshold:
            raise RuntimeError(
                f"player_stats has {row_count} rows which exceeds safe threshold ({threshold}). "
                "To force conversion during maintenance, set FORCE_PLAYER_STATS_HT=1 and re-run migration."
            )

    # Perform conversion and index creation in autocommit blocks (CONCURRENTLY requires no surrounding tx)
    with ctx.autocommit_block():
        # idempotent create_hypertable call
        try:
            op.execute(
                "SELECT create_hypertable('player_stats','created_at', if_not_exists => TRUE);"
            )
        except Exception as e:
            # If extension present but conversion fails, bubble up so operator can inspect logs.
            raise

    with ctx.autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_player_stats_player_created_at ON player_stats (player_id, created_at);"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_player_stats_created_at ON player_stats (created_at);"
        )


def downgrade() -> None:
    # Drop the indexes created above. Do NOT attempt to downgrade hypertable conversion.
    ctx = op.get_context()
    with ctx.autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_player_stats_player_created_at;"
        )
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_player_stats_created_at;")

    # Note: reversing a hypertable conversion is a destructive operation that should be handled
    # offline via DBA tools or a restore from backup. We intentionally do not revert hypertable status.
