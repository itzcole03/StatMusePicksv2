"""add feature_list to model_metadata

Revision ID: 0008_add_feature_list_model_metadata
Revises: 0007_add_team_stats
Create Date: 2025-11-25 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0008_add_feature_list_model_metadata"
down_revision = "0007_add_team_stats"
branch_labels = None
depends_on = None


def upgrade():
    # Add JSON column for feature_list (nullable)
    try:
        op.add_column(
            "model_metadata", sa.Column("feature_list", sa.JSON(), nullable=True)
        )
    except Exception:
        # Fallback for DBs without JSON support: create as Text
        op.add_column(
            "model_metadata", sa.Column("feature_list", sa.Text(), nullable=True)
        )


def downgrade():
    try:
        op.drop_column("model_metadata", "feature_list")
    except Exception:
        # best-effort
        pass
