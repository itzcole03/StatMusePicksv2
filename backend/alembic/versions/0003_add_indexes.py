"""add indexes for player_stats and predictions

Revision ID: 0003_add_indexes
Revises: 0002_add_game_stats_predictions
Create Date: 2025-11-11 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_add_indexes"
down_revision = "0002_add_game_stats_predictions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Create composite index for player_stats only if table exists and index missing
    if "player_stats" in inspector.get_table_names():
        existing = {idx["name"] for idx in inspector.get_indexes("player_stats")}
        if "ix_player_stats_player_id_game_id_created_at" not in existing:
            op.create_index(
                "ix_player_stats_player_id_game_id_created_at",
                "player_stats",
                ["player_id", "game_id", "created_at"],
                unique=False,
            )

    # Index predictions by player and creation timestamp for audit/history queries
    if "predictions" in inspector.get_table_names():
        existing_pred = {idx["name"] for idx in inspector.get_indexes("predictions")}
        if "ix_predictions_player_id_created_at" not in existing_pred:
            op.create_index(
                "ix_predictions_player_id_created_at",
                "predictions",
                ["player_id", "created_at"],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "predictions" in inspector.get_table_names():
        pred_indexes = {idx["name"] for idx in inspector.get_indexes("predictions")}
        if "ix_predictions_player_id_created_at" in pred_indexes:
            op.drop_index(
                "ix_predictions_player_id_created_at", table_name="predictions"
            )

    if "player_stats" in inspector.get_table_names():
        ps_indexes = {idx["name"] for idx in inspector.get_indexes("player_stats")}
        if "ix_player_stats_player_id_game_id_created_at" in ps_indexes:
            op.drop_index(
                "ix_player_stats_player_id_game_id_created_at",
                table_name="player_stats",
            )
