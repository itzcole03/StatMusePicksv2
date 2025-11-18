"""add calibration_metrics column to model_metadata

Revision ID: 0009_add_calibration_metrics
Revises: 0008_expand_alembic_version
Create Date: 2025-11-17 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

# revision identifiers, used by Alembic.
revision = '0009_add_calibration_metrics'
down_revision = '0008_expand_alembic_version'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name
    # Add a nullable calibration_metrics column. Use JSONB for Postgres,
    # JSON where available, otherwise fall back to Text storing JSON string.
    try:
        if dialect == 'postgresql':
            # Prefer JSONB for Postgres and add a GIN index for efficient JSON queries
            op.add_column('model_metadata', sa.Column('calibration_metrics', pg.JSONB(astext_type=sa.Text()), nullable=True))
            try:
                op.create_index('ix_model_metadata_calibration_metrics_gin', 'model_metadata', ['calibration_metrics'], postgresql_using='gin')
            except Exception:
                # best-effort: ignore index creation failures
                pass
        else:
            # SQLite and others: use TEXT to store a JSON blob
            op.add_column('model_metadata', sa.Column('calibration_metrics', sa.Text(), nullable=True))
    except Exception:
        # Best-effort: if add_column fails (e.g., column exists), continue
        try:
            # attempt a safe ALTER TABLE for dialects that support it
            if dialect != 'postgresql':
                op.add_column('model_metadata', sa.Column('calibration_metrics', sa.Text(), nullable=True))
        except Exception:
            pass


def downgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name
    try:
        if dialect == 'postgresql':
            try:
                op.drop_index('ix_model_metadata_calibration_metrics_gin', table_name='model_metadata')
            except Exception:
                pass
        op.drop_column('model_metadata', 'calibration_metrics')
    except Exception:
        # best-effort: ignore failures during downgrade
        pass
