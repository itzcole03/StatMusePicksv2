"""add indexes for player_stats and predictions

Revision ID: 0003_add_indexes
Revises: 0002_add_game_stats_predictions
Create Date: 2025-11-11 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0003_add_indexes'
down_revision = '0002_add_game_stats_predictions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create composite index for fast player time-range queries (use game_date)
    # Use existing columns on player_stats: player_id, game_id, created_at
    op.create_index(
        'ix_player_stats_player_id_game_id_created_at',
        'player_stats',
        ['player_id', 'game_id', 'created_at'],
        unique=False,
    )

    # Index predictions by player and creation timestamp for audit/history queries
    op.create_index('ix_predictions_player_id_created_at', 'predictions', ['player_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_predictions_player_id_created_at', table_name='predictions')
    op.drop_index('ix_player_stats_player_id_game_id_created_at', table_name='player_stats')
