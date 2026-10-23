"""Persist translated titles without changing the original title."""

import sqlalchemy as sa
from alembic import op

revision = "e62bc8c7a103"
down_revision = "c9d410f6dd23"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("articles", sa.Column("title_zh", sa.Text(), nullable=True))
    if op.get_bind().dialect.name == "postgresql":
        op.drop_index("ix_articles_fts", table_name="articles")
        op.execute("""CREATE INDEX ix_articles_fts ON articles USING gin
            (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(title_zh, '') || ' ' || coalesce(body, '') || ' ' || coalesce(summary_zh, '')))""")


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.drop_index("ix_articles_fts", table_name="articles")
        op.execute("""CREATE INDEX ix_articles_fts ON articles USING gin
            (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(body, '') || ' ' || coalesce(summary_zh, '')))""")
    op.drop_column("articles", "title_zh")
