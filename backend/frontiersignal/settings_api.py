import json
import os

from dotenv import set_key
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from .config import PROJECT_ROOT, Settings
from .models import Category

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
