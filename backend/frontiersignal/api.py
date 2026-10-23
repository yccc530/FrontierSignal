from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import Text, cast, func, select, text

from .collectors import COLLECTORS
from .models import AnalysisAttempt, Article, ArticleLink, RawRecord, Source, TaskRun
from .publishers import PUBLISHERS
from .queries import article_query
from .schemas import ArticleOut, ArticlePage, SourceOut, SourcePatch, TaskOut
from .topics import TOPICS, collection_topics

router = APIRouter(prefix="/api")


@router.get("/health")
async def health(request: Request):
    if request.app.state.tasks.owner_error:
        raise HTTPException(503, request.app.state.tasks.owner_error)
    async with request.app.state.db.sessions() as session:
        await session.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "database": request.app.state.db.engine.dialect.name,
        "scheduler": request.app.state.settings.scheduler_enabled,
        "llm_configured": request.app.state.settings.llm_configured,
    }


@router.get("/sources", response_model=list[SourceOut])
async def sources(request: Request):
    async with request.app.state.db.sessions() as session:
        return (
            await session.scalars(
                select(Source).where(Source.kind.in_(COLLECTORS)).order_by(Source.name)
            )
        ).all()


@router.post("/sources/{source_id}/collect", response_model=TaskOut, status_code=202)
async def collect(source_id: str, request: Request):
    try:
        return await request.app.state.tasks.submit(source_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None


@router.patch("/sources/{source_id}", response_model=SourceOut)
async def update_source(source_id: str, patch: SourcePatch, request: Request):
    async with request.app.state.tasks.lock, request.app.state.db.sessions() as session:
        source = await session.get(Source, source_id)
        if not source:
            raise HTTPException(404, "Source not found")
        if source.kind not in COLLECTORS:
            raise HTTPException(409, "该平台当前未接入")
        values = patch.model_dump(exclude_none=True)
        if "discovery_topics" in patch.model_fields_set:
            selected = patch.discovery_topics
            available = collection_topics(source.kind)
            if source.kind == "arxiv" and not source.config.get("research_queries"):
                available = []
            if not available or (
                selected is not None
                and (
                    len(set(selected)) != len(selected)
                    or any(key not in available for key in selected)
                )
            ):
                raise HTTPException(422, "该来源不支持所选采集方向")
            config = dict(source.config)
            if selected is None:
                config.pop("discovery_topics", None)
            else:
                config["discovery_topics"] = selected
            source.config = config
            values.pop("discovery_topics", None)
        if "automatic" in values:
            source.config = {**source.config, "automatic": values.pop("automatic")}
        for key, value in values.items():
            setattr(source, key, value)
        await session.commit()
        return source


@router.post("/collect", response_model=list[TaskOut], status_code=202)
async def collect_all(request: Request):
    async with request.app.state.db.sessions() as session:
        ids = (await session.scalars(select(Source.id).where(Source.enabled.is_(True)))).all()
    if not ids:
        raise HTTPException(409, "没有启用的信息源")
    runs = []
    for source_id in ids:
        try:
            runs.append(await request.app.state.tasks.submit(source_id))
        except ValueError:
            # A source may be disabled between listing and submission.
            continue
    if not runs:
        raise HTTPException(409, "未提交任务，来源可能已禁用或服务正在关闭")
    return runs


@router.get("/tasks", response_model=list[TaskOut])
async def tasks(request: Request):
    async with request.app.state.db.sessions() as session:
        return (
            await session.scalars(select(TaskRun).order_by(TaskRun.created_at.desc()).limit(100))
        ).all()


@router.get("/articles", response_model=ArticlePage)
async def articles(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str = Query("", max_length=200),
    source: str | None = None,
    category: str | None = None,
    favorite: bool | None = None,
    read: bool | None = None,
    status: Literal["pending", "processing", "analyzed", "filtered", "failed"] | None = None,
    sort: Literal["published", "score", "technical"] = "published",
    technical: bool | None = None,
    topic: str | None = None,
    content_type: Literal["models", "tools", "projects", "workflows", "papers", "datasets"]
    | None = None,
    publisher: str | None = None,
    after: datetime | None = None,
    before: datetime | None = None,
):
    after = after.replace(tzinfo=UTC) if after and after.tzinfo is None else after
    before = before.replace(tzinfo=UTC) if before and before.tzinfo is None else before
    if after and before and after >= before:
        raise HTTPException(422, "开始时间必须早于结束时间")
    if topic and topic not in TOPICS:
        raise HTTPException(422, "未知技术主题")
    if publisher and publisher not in PUBLISHERS:
        raise HTTPException(422, "未知发布团队")
    async with request.app.state.db.sessions() as session:
        query = article_query(
            q,
            source,
            category,
            favorite,
            read,
            status,
            after,
            before,
            request.app.state.db.engine.dialect.name,
        )
        if technical is not None:
            query = query.where(Article.technical_eligible.is_(technical))
        if topic:
            query = query.where(
                cast(Article.technical_topics, Text).contains(f'"{topic}"', autoescape=True)
            )
        if content_type == "models":
            query = query.where(Article.metrics["kind"].as_string().in_(["model", "model_release"]))
        elif content_type in {"tools", "projects", "workflows"}:
            types = {
                "tools": ["tool", "plugin", "framework", "client", "application"],
                "projects": ["project"],
                "workflows": ["workflow"],
            }[content_type]
            query = query.where(Article.metrics["resource"]["type"].as_string().in_(types))
        elif content_type == "papers":
            query = query.where(Article.source.has(kind="arxiv"))
        elif content_type == "datasets":
            query = query.where(Article.metrics["kind"].as_string() == "dataset")
        if publisher:
            query = query.where(Article.metrics["model"]["publisher_id"].as_string() == publisher)
        total = await session.scalar(select(func.count()).select_from(query.subquery()))
        ordering = [func.coalesce(Article.published_at, Article.collected_at).desc(), Article.id]
        if sort == "score":
            ordering.insert(0, Article.score.desc().nulls_last())
        elif sort == "technical":
            ordering.insert(0, Article.technical_score.desc())
        rows = (
            await session.scalars(
                query.order_by(*ordering).offset((page - 1) * page_size).limit(page_size)
            )
        ).all()
        return ArticlePage(
            items=[ArticleOut.model_validate(a) for a in rows],
            total=total,
            page=page,
            page_size=page_size,
        )


@router.get("/articles/{article_id}")
async def article(article_id: str, request: Request):
    async with request.app.state.db.sessions() as session:
        row = await session.get(Article, article_id)
        if not row:
            raise HTTPException(404, "Article not found")
        data = ArticleOut.model_validate(row).model_dump()
        data["raw_versions"] = await session.scalar(
            select(func.count()).select_from(RawRecord).where(RawRecord.article_id == row.id)
        )
        links = (
            await session.scalars(
                select(ArticleLink)
                .where((ArticleLink.left_id == row.id) | (ArticleLink.right_id == row.id))
                .limit(20)
            )
        ).all()
        related = []
        for link in links:
            other_id = link.right_id if link.left_id == row.id else link.left_id
            other = await session.get(Article, other_id)
            related.append(
                {
                    "id": other.id,
                    "title": other.title,
                    "title_zh": other.title_zh,
                    "source": other.source.name,
                    "method": link.method,
                    "similarity": link.similarity,
                }
            )
        data["related"] = related
        attempts = (
            await session.scalars(
                select(AnalysisAttempt)
                .where(AnalysisAttempt.article_id == row.id)
                .order_by(AnalysisAttempt.created_at.desc())
                .limit(20)
            )
        ).all()
        data["attempts"] = [
            {
                "id": a.id,
                "status": a.status,
                "model": a.model,
                "error": a.error,
                "created_at": a.created_at,
                "input_tokens": a.input_tokens,
                "output_tokens": a.output_tokens,
            }
            for a in attempts
        ]
        return data


@router.post("/analyze", response_model=TaskOut, status_code=202)
async def analyze_batch(request: Request):
    try:
        return await request.app.state.tasks.submit_analysis()
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None


@router.post("/articles/{article_id}/retry", response_model=TaskOut, status_code=202)
async def retry_article(article_id: str, request: Request):
    try:
        return await request.app.state.tasks.submit_analysis(article_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None


@router.post("/settings/probe", response_model=TaskOut, status_code=202)
async def probe_provider(request: Request):
    try:
        return await request.app.state.tasks.submit_probe()
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
