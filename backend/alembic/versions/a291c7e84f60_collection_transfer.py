"""Record measured collection response bodies without fabricating historical traffic."""

import sqlalchemy as sa
from alembic import op

revision = "a291c7e84f60"
down_revision = "7bd38f1a90c2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("task_runs", sa.Column("network_usage", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("task_runs", "network_usage")
