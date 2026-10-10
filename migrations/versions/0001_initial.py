"""Schemat początkowy: pytania, gry, zgadnięcia.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-10
"""
import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("location_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("image_filename", sa.String(255)),
        sa.Column("image_url", sa.String(1000)),
        sa.Column("image_credit", sa.String(500)),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_questions_category", "questions", ["category"])
    op.create_index("ix_questions_active", "questions", ["active"])

    op.create_table(
        "games",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("question_ids", sa.JSON(), nullable=False),
        sa.Column("current_round", sa.Integer(), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "guesses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.String(36), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id", ondelete="SET NULL")),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_guesses_game_id", "guesses", ["game_id"])


def downgrade():
    op.drop_table("guesses")
    op.drop_table("games")
    op.drop_table("questions")
