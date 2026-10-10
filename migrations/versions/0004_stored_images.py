import sqlalchemy as sa
from alembic import op

revision = "0004_stored_images"
down_revision = "0003_question_areas"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stored_images",
        sa.Column("name", sa.String(64), primary_key=True),
        sa.Column("mime", sa.String(32), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("stored_images")
