from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .topics import TOPICS


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    kind: str
    url: str
    enabled: bool
    automatic: bool
    interval_minutes: int
    trust: str
    last_run_at: datetime | None
    last_success_at: datetime | None
    last_status: str
    last_error: str | None
    discovery_topics: list[str]
    discovery_scope_customized: bool


class SourcePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = None
    automatic: bool | None = None
    interval_minutes: int | None = Field(None, ge=15, le=10080)
    discovery_topics: list[str] | None = Field(None, min_length=1, max_length=len(TOPICS))


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    source_id: str
    source: SourceOut
    title: str | None
    body: str
    original_url: str | None
    author: str | None
    published_at: datetime | None
    collected_at: datetime
    status: str
    is_read: bool
    is_favorite: bool
    title_zh: str | None
    summary_zh: str | None
    category: str | None
    tags: list[str] | None
    score: int | None
    is_ai_related: bool | None
    evidence: str | None
    analysis_model: str | None
    analyzed_at: datetime | None
    analysis_error: str | None
    embedding_error: str | None
    metrics: dict
    technical_score: int
    technical_topics: list[str]
    technical_reasons: list[str]
    technical_eligible: bool


class ArticlePage(BaseModel):
    items: list[ArticleOut]
    total: int
    page: int
    page_size: int


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    source_id: str | None
    kind: str
    status: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    added: int
    updated: int
    duplicates: int
    filtered: int
    failed: int
    error: str | None
