import json
import math
import os
from datetime import timedelta
from typing import Literal

from dotenv import set_key
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from .collectors.arxiv import research_groups
from .collectors.huggingface import dataset_groups, model_groups, model_query
from .config import PROJECT_ROOT
from .discovery_state import scan_rows
from .models import Repository, Source, StarSnapshot, WorkbenchState, now
from .observability import runtime_report
from .publishers import public_publishers
from .recommendation_state import RecommendationPolicy, load_policy, record_views
from .recommendations import ranked_projects, recommendation_dashboard
from .topics import CATALOG, TOPICS, public_topics

router = APIRouter(prefix="/api")


@router.get("/topics")
async def topics():
    return public_topics()


@router.get("/discovery/coverage")
async def discovery_coverage(request: Request):
    async with request.app.state.db.sessions() as session:
        sources = (
            await session.scalars(
                select(Source)
                .where(Source.kind.in_(["github_discovery", "hf_models", "hf_datasets", "arxiv"]))
                .order_by(Source.id)
            )
        ).all()
        result = []
        for source in sources:
            if not source.discovery_topics:
                continue
            groups = (
                [
                    {"id": key, "label": CATALOG[key].label, "topics": [key]}
                    for key in source.discovery_topics
                ]
                if source.kind == "github_discovery"
                else model_groups(source)
                if source.kind == "hf_models"
                else dataset_groups(source)
                if source.kind == "hf_datasets"
                else research_groups(source)
            )
            config = request.app.state.settings
            priority_rounds = None
            if source.kind == "hf_models":
                remaining = {group["id"] for group in groups}
                priority = {group["id"] for group in groups if group.get("priority")}
                start = (source.cursor or {}).get("model_tick", 0)
                requests = 0
                while remaining and requests < 10000:
                    group, _ = model_query(source, start + requests, 1)
                    remaining.discard(group["id"])
                    requests += 1
                    priority.discard(group["id"])
                    if (
                        not priority
                        and priority_rounds is None
                        and any(group.get("priority") for group in groups)
                    ):
                        priority_rounds = math.ceil(requests / config.hf_queries_per_run)
                rounds = math.ceil(requests / config.hf_queries_per_run)
                request_budget = config.hf_queries_per_run + config.hf_card_checks
            else:
                per_run = (
                    config.github_queries_per_run
                    if source.kind == "github_discovery"
                    else 3
                    if source.kind == "hf_datasets"
                    else 2
                )
                rounds = math.ceil(len(groups) / per_run)
                request_budget = (
                    (
                        config.github_queries_per_run
                        + 2 * config.github_track_per_run
                        + config.github_code_checks
                        + config.github_history_checks
                        + config.github_readme_checks
                    )
                    if source.kind == "github_discovery"
                    else per_run
                )
            result.append(
                {
                    "source_id": source.id,
                    "name": source.name,
                    "enabled": source.enabled,
                    "automatic": source.automatic,
                    "scan_cycle_hours": round(rounds * source.interval_minutes / 60, 1),
                    "request_budget": request_budget,
                    "priority_scan_hours": round(priority_rounds * source.interval_minutes / 60, 1)
                    if priority_rounds is not None
                    else None,
                    "groups": scan_rows(source, groups),
                }
            )
        return {"topics": public_topics(), "sources": result}


@router.get("/discovery/runtime")
async def runtime(request: Request):
    async with request.app.state.db.sessions() as session:
        return await runtime_report(session, request.app.state.settings, now())


@router.get("/recommendation-policy")
async def recommendation_policy(request: Request):
    async with request.app.state.db.sessions() as session:
        return await load_policy(session)


@router.patch("/recommendation-policy")
async def save_recommendation_policy(policy: RecommendationPolicy, request: Request):
    async with request.app.state.tasks.lock, request.app.state.db.sessions() as session:
        row = await session.get(WorkbenchState, "recommendations")
        if row:
            row.value = policy.model_dump()
        else:
            session.add(WorkbenchState(id="recommendations", value=policy.model_dump()))
        await session.commit()
        return policy


class Exposure(BaseModel):
    model_config = ConfigDict(extra="forbid")
    article_id: str = Field(min_length=36, max_length=36)
    revision_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class Exposures(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[Exposure] = Field(max_length=100)


@router.post("/recommendations/seen")
async def recommendation_seen(value: Exposures, request: Request):
    async with request.app.state.db.sessions() as session:
        count = await record_views(session, value.items, now())
        await session.commit()
        return {"recorded": count}


@router.get("/publishers")
async def publishers():
    return public_publishers()


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
    topics: list[str] = Field(min_length=1, max_length=len(TOPICS))


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
