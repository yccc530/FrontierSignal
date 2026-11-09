from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, case, func, select

from .models import AnalysisAttempt, Article, WorkbenchState, now


class ChineseSummaryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    all_content: bool = False


async def load_summary_policy(session):
    saved = await session.get(WorkbenchState, "chinese-summaries")
    return ChineseSummaryPolicy.model_validate(saved.value if saved else {})


def summary_ready():
    return and_(
        func.length(func.trim(func.coalesce(Article.title_zh, ""))) > 0,
        func.length(func.trim(func.coalesce(Article.summary_zh, ""))) > 0,
    )


def has_chinese_summary(article):
    return bool((article.title_zh or "").strip() and (article.summary_zh or "").strip())


async def summary_coverage(session, settings):
    policy = await load_summary_policy(session)
    running = (
        select(AnalysisAttempt.id)
        .where(
            AnalysisAttempt.article_id == Article.id,
            AnalysisAttempt.content_hash == Article.content_hash,
            AnalysisAttempt.status == "running",
        )
        .exists()
    )
    state = case(
        (summary_ready(), "ready"),
        (running | (Article.status == "processing"), "processing"),
        (Article.analysis_attempts >= 3, "failed"),
        (
            (Article.metrics["analysis_deferred_hash"].as_string() == Article.content_hash)
            & (not policy.all_content),
            "deferred",
        ),
        (Article.status.in_(["filtered", "analyzed"]) & (not policy.all_content), "excluded"),
        (Article.retry_at > now(), "retrying"),
        else_="queued",
    )
    counts = dict((await session.execute(select(state, func.count()).group_by(state))).all())
    return {
        "policy": policy.model_dump(),
        "automatic": settings.llm_configured and settings.scheduler_enabled,
        "batch_size": settings.llm_batch_size,
        "total": sum(counts.values()),
        **{
            key: counts.get(key, 0)
            for key in [
                "ready",
                "queued",
                "processing",
                "retrying",
                "failed",
                "deferred",
                "excluded",
            ]
        },
        "last_success_at": await session.scalar(
            select(func.max(AnalysisAttempt.finished_at)).where(AnalysisAttempt.status == "success")
        ),
    }
