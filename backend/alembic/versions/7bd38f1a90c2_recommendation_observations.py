"""Persist recommendation preferences, exposures and real runtime observations."""

import sqlalchemy as sa
from alembic import op

revision = "7bd38f1a90c2"
down_revision = "8ac491d20e63"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workbench_state",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
    )
    op.create_table(
        "recommendation_views",
        sa.Column("article_id", sa.String(36), sa.ForeignKey("articles.id"), primary_key=True),
        sa.Column("revision_hash", sa.String(64), primary_key=True),
        sa.Column("first_shown_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_shown_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_recommendation_views_last_shown_at", "recommendation_views", ["last_shown_at"]
    )
    op.create_table(
        "runtime_samples",
        sa.Column("slot", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduler_enabled", sa.Boolean(), nullable=False),
        sa.Column("active_tasks", sa.Integer(), nullable=False),
    )
    op.create_index("ix_task_source_created", "task_runs", ["source_id", "created_at"])


def downgrade():
    op.drop_index("ix_task_source_created", "task_runs")
    op.drop_table("runtime_samples")
    op.drop_table("recommendation_views")
    op.drop_table("workbench_state")
