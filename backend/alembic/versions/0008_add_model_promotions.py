"""add model_promotions table

Revision ID: 0008_add_model_promotions
Revises: 0007_add_team_stats
Create Date: 2025-11-13 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import func

# revision identifiers, used by Alembic.
revision = '0008_add_model_promotions'
down_revision = '0007_add_team_stats'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'model_promotions',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('player_name', sa.String(length=255), nullable=False),
        sa.Column('version', sa.String(length=64), nullable=True),
        sa.Column('promoted_by', sa.String(length=128), nullable=True),
        sa.Column('promoted_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column('notes', sa.Text, nullable=True),
    )
    # index to allow fast lookup by player
    op.create_index('ix_model_promotions_player_name', 'model_promotions', ['player_name'])


def downgrade():
    op.drop_index('ix_model_promotions_player_name', table_name='model_promotions')
    op.drop_table('model_promotions')
