"""merge 0008 heads

Revision ID: 0009_merge_0008
Revises: 0008_expand_alembic_version, 0008_add_model_promotions
Create Date: 2025-11-13 14:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0009_merge_0008'
down_revision = ('0008_expand_alembic_version', '0008_add_model_promotions')
branch_labels = None
depends_on = None


def upgrade():
    # This is a no-op merge revision to consolidate multiple heads so that
    # `alembic upgrade head` can be used in CI/test environments. All
    # structural changes have been implemented in the dependent revisions.
    pass


def downgrade():
    # No-op: downgrading a merge revision is not meaningful in this simple
    # test-friendly setup. If needed, manual downgrade steps should be added.
    pass
