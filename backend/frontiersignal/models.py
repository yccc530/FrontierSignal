import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


def now() -> datetime:
    return datetime.now(UTC)


def uid() -> str:
    return str(uuid.uuid4())


class UTCDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(40))
    url: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=120)
    trust: Mapped[str] = mapped_column(String(40), default="community")
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    cursor: Mapped[dict] = mapped_column(JSON, default=dict)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_success_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_status: Mapped[str] = mapped_column(String(30), default="never")
    last_error: Mapped[str | None] = mapped_column(Text)

    @property
    def automatic(self) -> bool:
        return (self.config or {}).get("automatic", True)


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("source_id", "identity_key", name="uq_article_source_identity"),
        UniqueConstraint("source_id", "canonical_url", name="uq_article_source_url"),
        Index("ix_article_source_hash", "source_id", "content_hash"),
        Index("ix_article_published", "published_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    source: Mapped[Source] = relationship(lazy="joined")
    identity_key: Mapped[str] = mapped_column(String(64))
    platform_id: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, default="")
    original_url: Mapped[str | None] = mapped_column(Text)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    collected_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    content_hash: Mapped[str] = mapped_column(String(64))
    fingerprint: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    title_zh: Mapped[str | None] = mapped_column(Text)
    summary_zh: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(80), index=True)
    tags: Mapped[list | None] = mapped_column(JSON)
    score: Mapped[int | None] = mapped_column(Integer, index=True)
    is_ai_related: Mapped[bool | None] = mapped_column(Boolean)
    evidence: Mapped[str | None] = mapped_column(Text)
    analysis_model: Mapped[str | None] = mapped_column(String(200))
    analysis_hash: Mapped[str | None] = mapped_column(String(64))
    analyzed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    analysis_error: Mapped[str | None] = mapped_column(Text)
    analysis_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    retry_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    embedding_error: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    technical_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    technical_topics: Mapped[list] = mapped_column(JSON, default=list)
    technical_reasons: Mapped[list] = mapped_column(JSON, default=list)
    technical_eligible: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class RawRecord(Base):
    __tablename__ = "raw_records"
    __table_args__ = (UniqueConstraint("article_id", "payload_hash", name="uq_raw_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id"), index=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    collected_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)


class TaskRun(Base):
    __tablename__ = "task_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"))
    kind: Mapped[str] = mapped_column(String(30), default="collect")
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now, index=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    added: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    filtered: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    label: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(400), default="")


class AnalysisAttempt(Base):
    __tablename__ = "analysis_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id"), index=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(200))
    prompt_version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    error: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    result: Mapped[dict | None] = mapped_column(JSON)


class ArticleLink(Base):
    __tablename__ = "article_links"
    __table_args__ = (UniqueConstraint("left_id", "right_id", name="uq_article_link"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    left_id: Mapped[str] = mapped_column(ForeignKey("articles.id"), index=True)
    right_id: Mapped[str] = mapped_column(ForeignKey("articles.id"), index=True)
    method: Mapped[str] = mapped_column(String(40))
    similarity: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)


class ArticleEmbedding(Base):
    __tablename__ = "article_embeddings"
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id"), primary_key=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(200), index=True)
    dimensions: Mapped[int] = mapped_column(Integer)
    vector: Mapped[list] = mapped_column(Vector().with_variant(JSON, "sqlite"))


class Repository(Base):
    __tablename__ = "repositories"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id"), unique=True)
    full_name: Mapped[str] = mapped_column(String(250), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(100))
    license: Mapped[str | None] = mapped_column(String(100))
    topics: Mapped[list] = mapped_column(JSON, default=list)
    stars: Mapped[int] = mapped_column(Integer)
    forks: Mapped[int] = mapped_column(Integer, default=0)
    size_kb: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    pushed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    last_tracked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)
    has_code: Mapped[bool | None] = mapped_column(Boolean)
    code_evidence: Mapped[list] = mapped_column(JSON, default=list)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    tracked: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    latest_release: Mapped[dict | None] = mapped_column(JSON)
    star_history: Mapped[dict | None] = mapped_column(JSON)


class StarSnapshot(Base):
    __tablename__ = "star_snapshots"
    __table_args__ = (
        UniqueConstraint("repository_id", "hour_bucket", name="uq_repository_snapshot_hour"),
        Index("ix_snapshot_repository_time", "repository_id", "observed_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id"))
    hour_bucket: Mapped[datetime] = mapped_column(UTCDateTime)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime)
    stars: Mapped[int] = mapped_column(Integer)
    forks: Mapped[int] = mapped_column(Integer)
