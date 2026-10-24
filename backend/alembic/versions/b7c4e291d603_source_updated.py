"""Keep observed Hub updates separate from publication and collection time."""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "b7c4e291d603"
down_revision = "a291c7e84f60"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "articles", sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True)
    )
    articles = sa.table(
        "articles",
        sa.column("id", sa.String),
        sa.column("source_id", sa.String),
        sa.column("metrics", sa.JSON),
        sa.column("source_updated_at", sa.DateTime(timezone=True)),
    )
    sources = sa.table("sources", sa.column("id", sa.String), sa.column("kind", sa.String))
    bind = op.get_bind()
    rows = bind.execute(
        sa.select(articles.c.id, articles.c.metrics)
        .join(sources, sources.c.id == articles.c.source_id)
        .where(sources.c.kind.in_(["hf_models", "hf_datasets"]))
    )
    for batch in rows.partitions(200):
        for identifier, metrics in batch:
            if not isinstance(metrics, dict):
                continue
            model = metrics.get("model") if isinstance(metrics.get("model"), dict) else {}
            value = model.get("hub_updated_at") or metrics.get("updated_at")
            if not isinstance(value, str):
                continue
            try:
                date = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                continue
            date = date.replace(tzinfo=UTC) if date.tzinfo is None else date.astimezone(UTC)
            bind.execute(
                articles.update().where(articles.c.id == identifier).values(source_updated_at=date)
            )


def downgrade():
    op.drop_column("articles", "source_updated_at")
