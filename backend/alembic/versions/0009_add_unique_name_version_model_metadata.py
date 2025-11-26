"""add unique index on model_metadata (name, version)

Revision ID: 0009_add_unique_name_version_model_metadata
Revises: 0008_add_feature_list_model_metadata
Create Date: 2025-11-25 00:10:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0009_add_unique_name_version_model_metadata"
down_revision = "0008_add_feature_list_model_metadata"
branch_labels = None
depends_on = None


def upgrade():
    # best-effort: add a unique index on (name, version)
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = [c["name"] for c in insp.get_columns("model_metadata")]
    if "name" in cols and "version" in cols:
        try:
            op.create_index(
                "uq_model_metadata_name_version",
                "model_metadata",
                ["name", "version"],
                unique=True,
            )
        except Exception:
            # If DB doesn't support unique index easily, skip
            pass


def downgrade():
    try:
        op.drop_index("uq_model_metadata_name_version", table_name="model_metadata")
    except Exception:
        pass
