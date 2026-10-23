import asyncio
import json
from datetime import timedelta

from sqlalchemy import case, func, or_, select

from .llm import PROMPT_VERSION, LLMProvider, ProviderError
from .models import AnalysisAttempt, Article, Category, now
from .normalizer import digest
from .semantic import store_and_link
from .similarity import link_related

DEFAULT_CATEGORIES = {
    "models": "模型发布与能力更新",
    "agents": "AI Agent 与开发框架",
    "research": "研究论文与技术突破",
    "opensource": "开源项目与开发工具",
    "products": "AI 产品与应用",
    "industry": "行业与商业动态",
    "safety": "安全、政策与治理",
}


async def seed_categories(session):
    for key, label in DEFAULT_CATEGORIES.items():
        if not await session.get(Category, key):
            session.add(Category(id=key, label=label))
    await session.commit()


class AnalysisPipeline:
    def __init__(self, db, settings, provider=None):
        self.db, self.settings = db, settings
        self.provider = provider or LLMProvider(settings)

    async def pending_ids(self):
        async with self.db.sessions() as session:
            return list(
                (
                    await session.scalars(
                        select(Article.id)
                        .where(
                            or_(
                                Article.status == "pending",
                                (Article.status == "failed") & (Article.analysis_attempts < 3),
                            ),
                            or_(Article.retry_at.is_(None), Article.retry_at <= now()),
                        )
                        .order_by(
                            case(
                                (
                                    Article.metrics["kind"].as_string() == "repository",
                                    Article.collected_at,
                                ),
                                else_=func.coalesce(Article.published_at, Article.collected_at),
                            ).desc(),
                            Article.id,
                        )
                        .limit(self.settings.llm_batch_size)
                    )
                ).all()
            )

    async def process(self, article_id: str) -> str:
        if not self.settings.llm_configured:
            raise ProviderError("尚未配置模型服务", retryable=False)
        async with self.db.sessions() as session:
            article = await session.get(Article, article_id)
            if not article:
                raise LookupError("Article not found")
            if article.status in {"analyzed", "filtered"}:
                return "skipped"
            categories = {c.id: c.label for c in (await session.scalars(select(Category))).all()}
            title, body, content_hash = article.title or "", article.body, article.content_hash
            request_hash = digest(
                json.dumps(
                    [
                        content_hash,
                        self.settings.llm_base_url,
                        self.settings.llm_model,
                        PROMPT_VERSION,
                        categories,
                    ],
                    sort_keys=True,
                )
            )
            if not article.technical_eligible:
                article.status, article.analysis_error = (
                    "filtered",
                    "技术筛选：缺少目标技术主题或实质技术证据",
                )
                await session.commit()
                return "filtered"
            keywords = self.settings.prefilter_keywords
            if keywords and not any(
                k.casefold() in (title + " " + body).casefold() for k in keywords
            ):
                article.status, article.analysis_error = (
                    "filtered",
                    "规则预筛选：未匹配配置的关键词",
                )
                await session.commit()
                return "filtered"
            article.status, article.analysis_error = "processing", None
            article.analysis_attempts += 1
            await session.commit()
            for retry in range(self.settings.llm_max_retries + 1):
                attempt = AnalysisAttempt(
                    article_id=article.id,
                    content_hash=content_hash,
                    request_hash=request_hash,
                    model=self.settings.llm_model,
                    prompt_version=PROMPT_VERSION,
                    status="running",
                )
                session.add(attempt)
                await session.commit()
                try:
                    completion = await self.provider.analyze(title, body, categories)
                    await session.refresh(article)
                    attempt.finished_at = now()
                    attempt.input_tokens, attempt.output_tokens = (
                        completion.input_tokens,
                        completion.output_tokens,
                    )
                    attempt.result = completion.result.model_dump()
                    if article.content_hash != content_hash:
                        attempt.status = "stale"
                        await session.commit()
                        return "stale"
                    result = completion.result
                    article.title_zh = result.title_zh
                    article.summary_zh, article.category, article.tags = (
                        result.summary_zh,
                        result.category,
                        result.tags,
                    )
                    article.score, article.is_ai_related, article.evidence = (
                        result.score,
                        result.is_ai_related,
                        result.evidence,
                    )
                    article.analysis_model, article.analysis_hash = (
                        self.settings.llm_model,
                        request_hash,
                    )
                    article.analyzed_at, article.retry_at, article.analysis_error = (
                        now(),
                        None,
                        None,
                    )
                    article.status = "analyzed" if result.is_ai_related else "filtered"
                    attempt.status = "success"
                    await link_related(session, article)
                    await session.commit()
                    if self.settings.embedding_model:
                        try:
                            vector = await self.provider.embed(title + "\n" + body)
                            await session.refresh(article)
                            if article.content_hash == content_hash:
                                await store_and_link(
                                    session,
                                    article,
                                    vector,
                                    self.settings.embedding_model,
                                    self.settings.semantic_threshold,
                                )
                                article.embedding_error = None
                                await session.commit()
                        except ProviderError as exc:
                            article.embedding_error = str(exc)
                            await session.commit()
                    return article.status
                except ProviderError as exc:
                    attempt.status, attempt.error, attempt.finished_at = "failed", str(exc), now()
                    await session.commit()
                    if not exc.retryable or retry == self.settings.llm_max_retries:
                        await session.refresh(article)
                        if article.content_hash == content_hash:
                            article.status, article.analysis_error = "failed", str(exc)
                            article.retry_at = now() + timedelta(
                                minutes=min(60, 2**article.analysis_attempts)
                            )
                            if not exc.retryable:
                                article.analysis_attempts = max(3, article.analysis_attempts)
                        await session.commit()
                        return "failed"
                    await asyncio.sleep(max(exc.delay, min(8, 2**retry)))
            raise AssertionError("unreachable")
