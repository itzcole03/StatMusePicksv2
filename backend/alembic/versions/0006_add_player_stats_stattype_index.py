"""add composite index for player_stats including stat_type

Revision ID: 0006_player_stats_st_idx
Revises: 0005_safe_player_stats_ht
Create Date: 2025-11-11 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0006_player_stats_st_idx'
down_revision = '0005_safe_player_stats_ht'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Composite index to support queries filtering by player, stat type and time range
    op.create_index(
        'ix_player_stats_player_id_game_id_stat_type',
        'player_stats',
        ['player_id', 'game_id', 'stat_type'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_player_stats_player_id_game_id_stat_type', table_name='player_stats')

