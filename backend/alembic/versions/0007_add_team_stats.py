"""create team_stats table

Revision ID: 0007_add_team_stats
Revises: 0006_add_player_stats_stattype_index
Create Date: 2025-11-12 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0007_add_team_stats'
down_revision = '0006_add_player_stats_stattype_index'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'team_stats',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('team', sa.String(length=64), nullable=False, index=True),
        sa.Column('season', sa.String(length=16), nullable=True, index=True),
        sa.Column('games_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('pts_for_avg', sa.Float(), nullable=True),
        sa.Column('pts_against_avg', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index(op.f('ix_team_stats_team'), 'team_stats', ['team'], unique=False)
    op.create_index(op.f('ix_team_stats_season'), 'team_stats', ['season'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_team_stats_season'), table_name='team_stats')
    op.drop_index(op.f('ix_team_stats_team'), table_name='team_stats')
    op.drop_table('team_stats')
