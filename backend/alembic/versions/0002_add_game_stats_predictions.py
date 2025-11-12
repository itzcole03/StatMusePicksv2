"""add games, player_stats, predictions tables

Revision ID: 0002_add_game_stats_predictions
Revises: 0001_initial
Create Date: 2025-11-11 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_add_game_stats_predictions'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'games',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('game_date', sa.DateTime, nullable=False),
        sa.Column('home_team', sa.String(length=64), nullable=False),
        sa.Column('away_team', sa.String(length=64), nullable=False),
        sa.Column('home_score', sa.Integer, nullable=True),
        sa.Column('away_score', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
    )

    op.create_table(
        'player_stats',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('player_id', sa.Integer, sa.ForeignKey('players.id'), nullable=False),
        sa.Column('game_id', sa.Integer, sa.ForeignKey('games.id'), nullable=False),
        sa.Column('stat_type', sa.String(length=64), nullable=False),
        sa.Column('value', sa.Float, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=True),
    )

    op.create_table(
        'predictions',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('player_id', sa.Integer, sa.ForeignKey('players.id'), nullable=False),
        sa.Column('stat_type', sa.String(length=64), nullable=False),
        sa.Column('predicted_value', sa.Float, nullable=False),
        sa.Column('actual_value', sa.Float, nullable=True),
        sa.Column('game_id', sa.Integer, sa.ForeignKey('games.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_table('predictions')
    op.drop_table('player_stats')
    op.drop_table('games')
