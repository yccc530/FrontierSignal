"""PostgreSQL full-text and chronological query indexes."""

from alembic import op

revision = "c9d410f6dd23"
down_revision = "8bf14a92f899"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""CREATE INDEX ix_articles_fts ON articles USING gin
            (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(body, '') || ' ' || coalesce(summary_zh, '')))""")
        op.execute(
            "CREATE INDEX ix_articles_timeline ON articles (coalesce(published_at, collected_at) DESC, id)"
        )


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP INDEX ix_articles_timeline")
        op.execute("DROP INDEX ix_articles_fts")
