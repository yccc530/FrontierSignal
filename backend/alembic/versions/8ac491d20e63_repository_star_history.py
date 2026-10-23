"""Keep official daily star observations separate from local net-change snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "8ac491d20e63"
down_revision = "4f6a329b8102"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("repositories", sa.Column("star_history", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("repositories", "star_history")
