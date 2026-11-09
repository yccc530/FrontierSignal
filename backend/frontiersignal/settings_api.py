import json
import os

from dotenv import set_key
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from .chinese_summaries import ChineseSummaryPolicy, summary_coverage, summary_ready
from .config import PROJECT_ROOT, Settings
from .models import AnalysisAttempt, Article, Category, TaskRun, WorkbenchState, now

router = APIRouter(prefix="/api")


class LLMSettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    llm_base_url: str = Field(max_length=500)
    llm_model: str = Field(max_length=200)
    llm_timeout: int = Field(ge=5, le=180)
    llm_max_retries: int = Field(ge=0, le=5)
    llm_batch_size: int = Field(ge=1, le=30)
    llm_json_mode: bool
    embedding_model: str = Field(default="", max_length=200)


def public_settings(config):
    return {
        **{key: getattr(config, key) for key in LLMSettingsPatch.model_fields},
        "llm_key_configured": bool(config.llm_api_key.get_secret_value()),
        "llm_configured": config.llm_configured,
        "github_token_configured": bool(config.github_token.get_secret_value()),
        "interest_topics": config.interest_topics,
        "github_queries_per_run": config.github_queries_per_run,
        "github_track_per_run": config.github_track_per_run,
        "proxy_configured": bool(config.outbound_proxy.get_secret_value()),
        "scheduler_enabled": config.scheduler_enabled,
        "config_file": ".env",
        "prefilter_keywords": config.prefilter_keywords,
        "semantic_threshold": config.semantic_threshold,
    }


@router.get("/settings")
async def read_settings(request: Request):
    return public_settings(request.app.state.settings)


@router.get("/chinese-summaries")
async def chinese_summaries(request: Request):
    async with request.app.state.db.sessions() as session:
        return await summary_coverage(session, request.app.state.settings)


@router.patch("/chinese-summaries")
async def save_chinese_summaries(value: ChineseSummaryPolicy, request: Request):
    async with request.app.state.tasks.lock, request.app.state.db.sessions() as session:
        row = await session.get(WorkbenchState, "chinese-summaries")
        if row:
            row.value = value.model_dump()
        else:
            session.add(WorkbenchState(id="chinese-summaries", value=value.model_dump()))
        await session.commit()
        return await summary_coverage(session, request.app.state.settings)


class SummaryRetry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    limit: int = Field(default=30, ge=1, le=100)


@router.post("/chinese-summaries/retry")
async def retry_chinese_summaries(value: SummaryRetry, request: Request):
    async with request.app.state.tasks.lock, request.app.state.db.sessions() as session:
        running = (
            select(AnalysisAttempt.id)
            .where(AnalysisAttempt.article_id == Article.id, AnalysisAttempt.status == "running")
            .exists()
        )
        rows = (
            await session.scalars(
                select(Article)
                .where(
                    ~summary_ready(),
                    Article.analysis_attempts >= 3,
                    Article.status != "processing",
                    ~running,
                )
                .order_by(
                    Article.technical_eligible.desc(), Article.collected_at.desc(), Article.id
                )
                .limit(value.limit)
            )
        ).all()
        for article in rows:
            article.analysis_attempts, article.retry_at, article.analysis_error = 0, None, None
        run = TaskRun(
            kind="summary_retry",
            status="success",
            updated=len(rows),
            started_at=now(),
            finished_at=now(),
        )
        session.add(run)
        await session.commit()
        return {"queued": len(rows), "limit": value.limit, "task_id": run.id}


@router.patch("/settings")
async def update_settings(patch: LLMSettingsPatch, request: Request):
    manager = request.app.state.tasks
    async with manager.lock:
        if manager.analysis_running:
            raise HTTPException(409, "分析任务运行时不能修改模型配置")
        values = patch.model_dump()
        if any("\n" in v or "\r" in v for v in values.values() if isinstance(v, str)):
            raise HTTPException(422, "配置值不能包含换行")
        try:
            updated = Settings.model_validate({**request.app.state.settings.model_dump(), **values})
        except ValueError:
            raise HTTPException(
                422, "模型地址必须是无凭据的 HTTPS 地址，或本机 HTTP 地址"
            ) from None
        for key in values:
            if f"FS_{key.upper()}" in os.environ:
                raise HTTPException(409, "配置受进程环境变量管理，请在启动环境修改")
        path = PROJECT_ROOT / ".env"
        for key, value in values.items():
            encoded = str(value) if isinstance(value, str) else json.dumps(value)
            set_key(str(path), f"FS_{key.upper()}", encoded, quote_mode="always")
        path.chmod(0o600)
        request.app.state.settings = updated
        manager.settings, manager.fetcher.settings = updated, updated
        return public_settings(updated)


@router.get("/categories")
async def categories(request: Request):
    async with request.app.state.db.sessions() as session:
        rows = (await session.scalars(select(Category).order_by(Category.id))).all()
        return [{"id": row.id, "label": row.label, "description": row.description} for row in rows]


class CategoryInput(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,79}$")
    label: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=400)


@router.post("/categories", status_code=201)
async def save_category(value: CategoryInput, request: Request):
    async with request.app.state.db.sessions() as session:
        await session.merge(Category(**value.model_dump()))
        await session.commit()
        return value
