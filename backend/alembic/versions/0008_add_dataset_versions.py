"""add dataset_versions table

Revision ID: 0008_add_dataset_versions
Revises:
Create Date: 2025-11-18 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0008_add_dataset_versions"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("version_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("git_sha", sa.String(length=128), nullable=True),
        sa.Column("seasons", sa.Text(), nullable=True),
        sa.Column("rows_train", sa.Integer, nullable=True),
        sa.Column("rows_val", sa.Integer, nullable=True),
        sa.Column("rows_test", sa.Integer, nullable=True),
        sa.Column("uid", sa.String(length=64), nullable=True),
        sa.Column("manifest", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_table("dataset_versions")
