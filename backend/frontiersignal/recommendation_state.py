import json
from datetime import timedelta

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select

from .models import Article, RecommendationView, WorkbenchState
from .normalizer import digest
from .topics import CATALOG

SECTION_LIMITS = {
    "models": 6,
    "tools": 6,
    "workflows": 4,
    "hot": 6,
    "papers": 6,
    "official": 6,
    "discoveries": 6,
}


class RecommendationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    section_limits: dict[str, int] = Field(default_factory=lambda: dict(SECTION_LIMITS))
    topic_weights: dict[str, int] = Field(default_factory=dict)
    repeat_hours: int = Field(24, ge=1, le=168)

    @field_validator("section_limits", "topic_weights")
    @classmethod
    def valid_map(cls, value, info):
        allowed, low, high = (
            (SECTION_LIMITS, 0, 12) if info.field_name == "section_limits" else (CATALOG, 1, 5)
        )
        if any(
            key not in allowed or isinstance(weight, bool) or not low <= weight <= high
            for key, weight in value.items()
        ):
            raise ValueError("未知栏目/主题或份额超出范围")
        return value


async def load_policy(session):
    saved = await session.get(WorkbenchState, "recommendations")
    policy = RecommendationPolicy.model_validate(saved.value if saved else {})
    policy.section_limits = {**SECTION_LIMITS, **policy.section_limits}
    return policy


def revision_hash(article):
    metrics = article.metrics or {}
    model, resource = metrics.get("model") or {}, metrics.get("resource") or {}
    return digest(
        json.dumps(
            [
                article.content_hash,
                model.get("revision"),
                model.get("version"),
                model.get("release_status"),
                resource.get("readme_sha"),
            ]
        )
    )


async def exposure_state(session, articles, at, hours):
    views = (
        (
            await session.scalars(
                select(RecommendationView).where(
                    RecommendationView.article_id.in_([row.id for row in articles]),
                )
            )
        ).all()
        if articles
        else []
    )
    by_id = {}
    for view in views:
        by_id.setdefault(view.article_id, []).append(view)
    states = {}
    for article in articles:
        fingerprint = revision_hash(article)
        history = by_id.get(article.id, [])
        matching = next((row for row in history if row.revision_hash == fingerprint), None)
        recent = bool(matching and matching.last_shown_at >= at - timedelta(hours=hours))
        states[article.id] = {
            "revision_hash": fingerprint,
            "recent": recent,
            "status": "unchanged"
            if recent
            else "updated"
            if history and not matching
            else "new"
            if not history
            else "revisit",
        }
    return states


async def record_views(session, entries, at):
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    insert = pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
    rows = (
        await session.scalars(
            select(Article).where(Article.id.in_([e.article_id for e in entries]))
        )
    ).all()
    signatures = {entry.article_id: entry.revision_hash for entry in entries}
    accepted = 0
    for article in rows:
        fingerprint = revision_hash(article)
        if signatures[article.id] != fingerprint:
            continue
        await session.execute(
            insert(RecommendationView)
            .values(
                article_id=article.id,
                revision_hash=fingerprint,
                first_shown_at=at,
                last_shown_at=at,
                count=1,
            )
            .on_conflict_do_update(
                index_elements=["article_id", "revision_hash"],
                set_={
                    "last_shown_at": at,
                    "count": RecommendationView.count + 1,
                },
            )
        )
        accepted += 1
    return accepted
