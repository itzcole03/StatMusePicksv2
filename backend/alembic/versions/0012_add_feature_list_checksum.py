"""add feature_list_checksum to model_metadata

Revision ID: 0012_add_feature_list_checksum
Revises: 0011_merge_0010s
Create Date: 2025-11-26 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0012_add_feature_list_checksum"
# This migration merges the remaining 0010 head into the linear history
# by depending on both the 0011 merge and the remaining 0010 head.
down_revision = ("0011_merge_0010s", "0010_enforce_unique_name_version_constraint")
branch_labels = None
depends_on = None


def upgrade():
    # Add nullable checksum column for quick client-side validation
    try:
        op.add_column(
            "model_metadata",
            sa.Column("feature_list_checksum", sa.String(length=128), nullable=True),
        )
    except Exception:
        # best-effort
        pass


def downgrade():
    try:
        op.drop_column("model_metadata", "feature_list_checksum")
    except Exception:
        pass
