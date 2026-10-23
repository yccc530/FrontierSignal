import re
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, func, select

from .models import AnalysisAttempt, Article, RawRecord, Source, TaskRun, uid
from .network import validate_feed_url
from .schemas import ArticleOut, SourceOut

router = APIRouter(prefix="/api")


class ArticlePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_read: bool | None = None
    is_favorite: bool | None = None


@router.patch("/articles/{article_id}", response_model=ArticleOut)
async def update_article(article_id: str, value: ArticlePatch, request: Request):
    async with request.app.state.db.sessions() as session:
        article = await session.get(Article, article_id)
        if not article:
            raise HTTPException(404, "Article not found")
        for key, field in value.model_dump(exclude_none=True).items():
            setattr(article, key, field)
        await session.commit()
        return article


@router.get("/articles/{article_id}/raw")
async def raw_records(article_id: str, request: Request):
    async with request.app.state.db.sessions() as session:
        if not await session.get(Article, article_id):
            raise HTTPException(404, "Article not found")
        rows = (
            await session.scalars(
                select(RawRecord)
                .where(RawRecord.article_id == article_id)
                .order_by(RawRecord.collected_at.desc())
                .limit(5)
            )
        ).all()
        return [
            {
                "id": row.id,
                "collected_at": row.collected_at,
                "payload_hash": row.payload_hash,
                "payload": row.payload,
            }
            for row in rows
        ]


@router.get("/stats")
async def stats(request: Request):
    async with request.app.state.db.sessions() as session:
        row = (
            await session.execute(
                select(
                    func.count(),
                    func.sum(case((Article.is_favorite.is_(True), 1), else_=0)),
                    func.sum(case((Article.is_read.is_(False), 1), else_=0)),
                    func.sum(case((Article.status == "pending", 1), else_=0)),
                    func.sum(case((Article.status == "analyzed", 1), else_=0)),
                    func.sum(case((Article.status == "failed", 1), else_=0)),
                ).select_from(Article)
            )
        ).one()
        totals = dict(
            zip(
                ["total", "favorites", "unread", "pending", "analyzed", "failed"],
                [v or 0 for v in row],
                strict=True,
            )
        )
        totals["enabled_sources"] = await session.scalar(
            select(func.count()).select_from(Source).where(Source.enabled.is_(True))
        )
        totals["active_tasks"] = await session.scalar(
            select(func.count())
            .select_from(TaskRun)
            .where(TaskRun.status.in_(["queued", "running"]))
        )
        totals["input_tokens"] = await session.scalar(
            select(func.sum(AnalysisAttempt.input_tokens))
        )
        totals["output_tokens"] = await session.scalar(
            select(func.sum(AnalysisAttempt.output_tokens))
        )
        totals["last_collection"] = await session.scalar(
            select(func.max(TaskRun.finished_at)).where(
                TaskRun.kind == "collect", TaskRun.status == "success"
            )
        )
        return totals


class SourceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    kind: Literal[
        "rss", "github", "arxiv", "hackernews", "github_discovery", "hf_models", "hf_datasets"
    ]
    url: str = Field(default="", max_length=1000)
    repository: str = Field(default="", max_length=200)
    automatic: bool | None = None
    interval_minutes: int = Field(default=120, ge=15, le=10080)


@router.post("/sources", response_model=SourceOut, status_code=201)
async def create_source(value: SourceInput, request: Request):
    config, trust, url = {}, "unreviewed", value.url
    if value.kind == "github":
        if not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", value.repository
        ):
            raise HTTPException(422, "GitHub 项目格式应为 owner/repository")
        config, trust = {"repository": value.repository}, "maintainer"
        url = f"https://api.github.com/repos/{value.repository}/releases"
    elif value.kind == "hackernews":
        url, trust = "https://hacker-news.firebaseio.com/v0/topstories.json", "community"
    elif value.kind == "github_discovery":
        url, trust = "https://api.github.com/search/repositories", "maintainer"
    elif value.kind in {"hf_models", "hf_datasets"}:
        family = "models" if value.kind == "hf_models" else "datasets"
        url, trust = f"https://huggingface.co/api/{family}", "community"
    elif value.kind == "arxiv":
        if not re.fullmatch(r"https://rss.arxiv.org/rss/[A-Za-z.]+", url):
            raise HTTPException(422, "arXiv 地址应为官方分类 RSS")
        trust = "preprint"
    config["automatic"] = value.automatic if value.automatic is not None else True
    try:
        validate_feed_url(url, request.app.state.tasks.fetcher.hosts)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    async with request.app.state.db.sessions() as session:
        existing = (await session.scalars(select(Source).where(Source.url == url))).all()
        if existing:
            raise HTTPException(409, "该来源已存在")
        if (await session.scalar(select(func.count()).select_from(Source))) >= 100:
            raise HTTPException(409, "本地版本最多配置 100 个来源")
        source = Source(
            id=uid(),
            name=value.name.strip(),
            kind=value.kind,
            url=url,
            config=config,
            trust=trust,
            interval_minutes=value.interval_minutes,
            enabled=True,
        )
        session.add(source)
        await session.commit()
        return source
