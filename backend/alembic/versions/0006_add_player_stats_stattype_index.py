"""add composite index for player_stats including stat_type

Revision ID: 0006_add_player_stats_stattype_index
Revises: 0005_safe_player_stats_ht
Create Date: 2025-11-11 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0006_add_player_stats_stattype_index'
down_revision = '0005_safe_player_stats_ht'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Create composite index only if the table exists and index not present
    if 'player_stats' in inspector.get_table_names():
        existing = {idx['name'] for idx in inspector.get_indexes('player_stats')}
        if 'ix_player_stats_player_id_game_id_stat_type' not in existing:
            op.create_index(
                'ix_player_stats_player_id_game_id_stat_type',
                'player_stats',
                ['player_id', 'game_id', 'stat_type'],
                unique=False,
            )
    else:
        # Table not present (maybe created elsewhere); skip creating index for now.
        pass


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'player_stats' in inspector.get_table_names():
        indexes = {idx['name'] for idx in inspector.get_indexes('player_stats')}
        if 'ix_player_stats_player_id_game_id_stat_type' in indexes:
            op.drop_index('ix_player_stats_player_id_game_id_stat_type', table_name='player_stats')

