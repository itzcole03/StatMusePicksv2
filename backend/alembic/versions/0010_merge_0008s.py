"""merge two 0008 heads into a single linear history

Revision ID: 0010_merge_0008s
Revises: 0008_add_dataset_versions, 0008_expand_alembic_version
Create Date: 2025-11-19 16:30:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '0010_merge_0008s'
down_revision = ('0008_add_dataset_versions', '0008_expand_alembic_version')
branch_labels = None
depends_on = None


def upgrade():
    # merge-only revision: no DB changes required, this just consolidates heads
    pass


def downgrade():
    # irreversible no-op for downgrade
    pass
