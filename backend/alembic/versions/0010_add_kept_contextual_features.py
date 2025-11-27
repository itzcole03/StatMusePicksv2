"""add kept_contextual_features column to model_metadata

Revision ID: 0010_add_kept_contextual_features
Revises: 0009_add_calibration_metrics
Create Date: 2025-11-24 12:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

# revision identifiers, used by Alembic.
revision = "0010_add_kept_contextual_features"
down_revision = "0009_add_calibration_metrics"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name
    try:
        if dialect == "postgresql":
            op.add_column(
                "model_metadata",
                sa.Column(
                    "kept_contextual_features",
                    pg.JSONB(astext_type=sa.Text()),
                    nullable=True,
                ),
            )
            try:
                op.create_index(
                    "ix_model_metadata_kept_ctx_gin",
                    "model_metadata",
                    ["kept_contextual_features"],
                    postgresql_using="gin",
                )
            except Exception:
                pass
        else:
            # Fallback for SQLite/others: store as TEXT
            op.add_column(
                "model_metadata",
                sa.Column("kept_contextual_features", sa.Text(), nullable=True),
            )
    except Exception:
        # Best-effort: ignore failures if column exists
        pass


def downgrade():
    try:
        bind = op.get_bind()
        dialect = bind.dialect.name
        if dialect == "postgresql":
            try:
                op.drop_index(
                    "ix_model_metadata_kept_ctx_gin", table_name="model_metadata"
                )
            except Exception:
                pass
        op.drop_column("model_metadata", "kept_contextual_features")
    except Exception:
        pass
