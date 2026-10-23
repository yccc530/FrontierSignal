"""Technical signals, repository discovery and observed star history."""

import sqlalchemy as sa
from alembic import op

revision = "4f6a329b8102"
down_revision = "e62bc8c7a103"
branch_labels = None
depends_on = None


def upgrade():
    for name, default in [
        ("metrics", "{}"),
        ("technical_topics", "[]"),
        ("technical_reasons", "[]"),
    ]:
        op.add_column(
            "articles", sa.Column(name, sa.JSON(), nullable=False, server_default=default)
        )
    op.add_column(
        "articles", sa.Column("technical_score", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "articles",
        sa.Column("technical_eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_articles_technical_score", "articles", ["technical_score"])
    op.create_index("ix_articles_technical_eligible", "articles", ["technical_eligible"])
    op.create_table(
        "repositories",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column(
            "article_id", sa.String(36), sa.ForeignKey("articles.id"), nullable=False, unique=True
        ),
        sa.Column("full_name", sa.String(250), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("language", sa.String(100)),
        sa.Column("license", sa.String(100)),
        sa.Column("topics", sa.JSON(), nullable=False),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.Column("forks", sa.Integer(), nullable=False),
        sa.Column("size_kb", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("pushed_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_tracked_at", sa.DateTime(timezone=True)),
        sa.Column("has_code", sa.Boolean()),
        sa.Column("code_evidence", sa.JSON(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("tracked", sa.Boolean(), nullable=False),
        sa.Column("latest_release", sa.JSON()),
    )
    for field in ("full_name", "pushed_at", "observed_at", "last_tracked_at", "tracked"):
        op.create_index(f"ix_repositories_{field}", "repositories", [field])
    op.create_table(
        "star_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("repository_id", sa.String(80), sa.ForeignKey("repositories.id"), nullable=False),
        sa.Column("hour_bucket", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.Column("forks", sa.Integer(), nullable=False),
        sa.UniqueConstraint("repository_id", "hour_bucket", name="uq_repository_snapshot_hour"),
    )
    op.create_index(
        "ix_snapshot_repository_time", "star_snapshots", ["repository_id", "observed_at"]
    )


def downgrade():
    op.drop_table("star_snapshots")
    op.drop_table("repositories")
    op.drop_index("ix_articles_technical_eligible", table_name="articles")
    op.drop_index("ix_articles_technical_score", table_name="articles")
    for name in (
        "technical_eligible",
        "technical_score",
        "technical_reasons",
        "technical_topics",
        "metrics",
    ):
        op.drop_column("articles", name)
