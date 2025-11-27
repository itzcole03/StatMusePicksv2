"""initial migration

Revision ID: 0001_initial
Revises:
Create Date: 2025-11-10 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "players" not in inspector.get_table_names():
        op.create_table(
            "players",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("nba_player_id", sa.Integer, nullable=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("team", sa.String(length=64), nullable=True),
            sa.Column("position", sa.String(length=32), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=True),
        )

    if "projections" not in inspector.get_table_names():
        op.create_table(
            "projections",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "player_id", sa.Integer, sa.ForeignKey("players.id"), nullable=False
            ),
            sa.Column("source", sa.String(length=128), nullable=True),
            sa.Column("stat", sa.String(length=64), nullable=False),
            sa.Column("line", sa.Float, nullable=False),
            sa.Column("projection_at", sa.DateTime, nullable=True),
            sa.Column("raw", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=True),
        )

    if "model_metadata" not in inspector.get_table_names():
        op.create_table(
            "model_metadata",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("version", sa.String(length=64), nullable=True),
            sa.Column("path", sa.String(length=512), nullable=True),
            sa.Column("notes", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "model_metadata" in inspector.get_table_names():
        op.drop_table("model_metadata")
    if "projections" in inspector.get_table_names():
        op.drop_table("projections")
    if "players" in inspector.get_table_names():
        op.drop_table("players")
