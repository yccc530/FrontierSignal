import json
import os
from datetime import timedelta
from typing import Literal

from dotenv import set_key
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from .config import PROJECT_ROOT
from .models import Repository, StarSnapshot, now
from .recommendations import ranked_projects, recommendation_dashboard
from .technical import TOPICS

router = APIRouter(prefix="/api")


@router.get("/topics")
async def topics():
    return [{"id": key, "label": label} for key, (label, _) in TOPICS.items()]


def validate_topic(topic):
    if topic and topic not in TOPICS:
        raise HTTPException(422, "未知技术主题")


@router.get("/recommendations")
async def recommendations(request: Request, topic: str | None = None):
    validate_topic(topic)
    async with request.app.state.db.sessions() as session:
        return await recommendation_dashboard(
            session, now(), request.app.state.settings.interest_topics, topic
        )


@router.get("/projects")
async def projects(
    request: Request,
    q: str = Query("", max_length=200),
    topic: str | None = None,
    pool: Literal["rising", "new", "all"] = "rising",
    sort: Literal["recommended", "stars", "growth24", "growth7", "updated"] = "recommended",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    validate_topic(topic)
    async with request.app.state.db.sessions() as session:
        items, truncated = await ranked_projects(
            session, now(), request.app.state.settings.interest_topics, topic, q
        )
        counts = {
            "all": len(items),
            "rising": sum(row["momentum"]["is_rising"] for row in items),
            "new": sum(row["momentum"]["is_new"] for row in items),
        }
        if pool != "all":
            field = "is_rising" if pool == "rising" else "is_new"
            items = [row for row in items if row["momentum"][field]]
        if sort in {"growth24", "growth7"}:
            field = "growth_24h" if sort == "growth24" else "growth_7d"
            items.sort(
                key=lambda row: (
                    row[field]["value"] is None,
                    -(row[field]["value"] or 0),
                    row["id"],
                )
            )
        elif sort == "stars":
            items.sort(key=lambda row: (-row["stars"], row["id"]))
        elif sort == "updated":
            items.sort(
                key=lambda row: (
                    row["pushed_at"] is None,
                    -(row["pushed_at"].timestamp() if row["pushed_at"] else 0),
                    row["id"],
                )
            )
        start = (page - 1) * page_size
        return {
            "items": items[start : start + page_size],
            "total": len(items),
            "page": page,
            "page_size": page_size,
            "truncated": truncated,
            "counts": counts,
            "pool": pool,
        }


@router.get("/projects/{repository_id}/history")
async def history(repository_id: str, request: Request):
    async with request.app.state.db.sessions() as session:
        if not await session.get(Repository, repository_id):
            raise HTTPException(404, "项目不存在")
        rows = (
            await session.scalars(
                select(StarSnapshot)
                .where(
                    StarSnapshot.repository_id == repository_id,
                    StarSnapshot.observed_at >= now() - timedelta(days=30),
                )
                .order_by(StarSnapshot.observed_at.desc())
                .limit(720)
            )
        ).all()
        return [
            {"observed_at": row.observed_at, "stars": row.stars, "forks": row.forks}
            for row in reversed(rows)
        ]


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topics: list[str] = Field(min_length=1, max_length=8)


@router.patch("/preferences")
async def preferences(value: Preferences, request: Request):
    for topic in value.topics:
        validate_topic(topic)
    if len(set(value.topics)) != len(value.topics) or any(not topic for topic in value.topics):
        raise HTTPException(422, "研究偏好不能重复或为空")
    if "FS_INTEREST_TOPICS" in os.environ:
        raise HTTPException(409, "研究偏好由进程环境变量管理，请修改启动环境")
    async with request.app.state.tasks.lock:
        config = request.app.state.settings.model_copy(update={"interest_topics": value.topics})
        path = PROJECT_ROOT / ".env"
        set_key(str(path), "FS_INTEREST_TOPICS", json.dumps(value.topics), quote_mode="always")
        path.chmod(0o600)
        request.app.state.settings = config
        request.app.state.tasks.settings = request.app.state.tasks.fetcher.settings = config
        return {"topics": config.interest_topics}
