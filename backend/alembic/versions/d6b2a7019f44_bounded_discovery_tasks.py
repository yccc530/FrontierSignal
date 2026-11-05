"""Keep bounded backfill requests and page-level coverage evidence."""

import sqlalchemy as sa
from alembic import op

revision = "d6b2a7019f44"
down_revision = "b7c4e291d603"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("task_runs", sa.Column("details", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("task_runs", "details")
