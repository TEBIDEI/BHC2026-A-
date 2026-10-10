import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography

revision = "0003_question_areas"
down_revision = "0002_accounts_sets_ranking"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.add_column(
        "questions", sa.Column("area_level", sa.String(16), nullable=False, server_default="punkt")
    )
    op.add_column(
        "questions",
        sa.Column("area", Geography("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=True),
    )
    op.create_index("idx_questions_area", "questions", ["area"], postgresql_using="gist")


def downgrade():
    op.drop_index("idx_questions_area", "questions")
    op.drop_column("questions", "area")
    op.drop_column("questions", "area_level")
