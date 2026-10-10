"""Konta graczy, zestawy pytań, karta faktów, rankingi.

Revision ID: 0002_accounts_sets_ranking
Revises: 0001_initial
Create Date: 2026-10-10
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_accounts_sets_ranking"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(32), nullable=False),
        sa.Column("username_key", sa.String(32), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "question_sets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "set_questions",
        sa.Column("set_id", sa.Integer(), sa.ForeignKey("question_sets.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True),
    )

    op.add_column("questions", sa.Column("facts", sa.JSON(), nullable=False, server_default="[]"))

    op.add_column("games", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")))
    op.add_column("games", sa.Column("set_id", sa.Integer(), sa.ForeignKey("question_sets.id", ondelete="SET NULL")))
    op.add_column("games", sa.Column("ranked", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("games", sa.Column("finished_at", sa.DateTime(timezone=True)))
    op.create_index("ix_games_user_id", "games", ["user_id"])
    op.create_index("ix_games_set_id", "games", ["set_id"])
    op.create_index("ix_games_finished_at", "games", ["finished_at"])


def downgrade():
    op.drop_index("ix_games_finished_at", "games")
    op.drop_index("ix_games_set_id", "games")
    op.drop_index("ix_games_user_id", "games")
    op.drop_column("games", "finished_at")
    op.drop_column("games", "ranked")
    op.drop_column("games", "set_id")
    op.drop_column("games", "user_id")
    op.drop_column("questions", "facts")
    op.drop_table("set_questions")
    op.drop_table("question_sets")
    op.drop_table("users")
