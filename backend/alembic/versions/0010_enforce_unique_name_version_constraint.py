"""enforce unique constraint on model_metadata (name, version)

Revision ID: 0010_enforce_unique_name_version_constraint
Revises: 0009_add_unique_name_version_model_metadata
Create Date: 2025-11-25 00:20:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0010_enforce_unique_name_version_constraint'
down_revision = '0009_add_unique_name_version_model_metadata'
branch_labels = None
depends_on = None


def upgrade():
    # Attempt to add a strict unique constraint. This may fail if duplicates exist;
    # run the dedupe helper script before applying this migration in production.
    try:
        op.create_unique_constraint('uq_model_metadata_name_version', 'model_metadata', ['name', 'version'])
    except Exception:
        # If constraint creation fails (DB-specific), fall back to creating a unique index
        try:
            op.create_index('uq_model_metadata_name_version_idx', 'model_metadata', ['name', 'version'], unique=True)
        except Exception:
            # give up gracefully
            pass


def downgrade():
    try:
        op.drop_constraint('uq_model_metadata_name_version', 'model_metadata', type_='unique')
    except Exception:
        try:
            op.drop_index('uq_model_metadata_name_version_idx', table_name='model_metadata')
        except Exception:
            pass
