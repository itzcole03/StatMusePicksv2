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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'team_stats' not in inspector.get_table_names():
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
    else:
        # table already exists (possibly created by model metadata or a previous
        # partial migration run). Skip creation to keep migration idempotent.
        pass


    # Note: `index=True` on the Column definition above will create
    # the indexes during table creation for many dialects. Avoid
    # duplicate `op.create_index` calls which raise on SQLite.


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Drop indexes only if they exist
    indexes = {idx['name'] for idx in inspector.get_indexes('team_stats')} if 'team_stats' in inspector.get_table_names() else set()
    if 'ix_team_stats_season' in indexes:
        op.drop_index(op.f('ix_team_stats_season'), table_name='team_stats')
    if 'ix_team_stats_team' in indexes:
        op.drop_index(op.f('ix_team_stats_team'), table_name='team_stats')

    if 'team_stats' in inspector.get_table_names():
        op.drop_table('team_stats')
