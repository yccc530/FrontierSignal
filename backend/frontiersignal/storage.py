import asyncio
import json

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .content_info import content_metadata
from .models import Article, RawRecord, Source, now
from .normalizer import RawItem, digest, normalize
from .projects import store_repository
from .technical import technical_signal


async def ingest(session: AsyncSession, source: Source, item: RawItem) -> tuple[Article, str]:
    values = await asyncio.to_thread(normalize, item)
    conditions = [Article.identity_key == values["identity_key"]]
    if values["canonical_url"]:
        conditions.append(Article.canonical_url == values["canonical_url"])
    if len(values["body"]) >= 80 and source.kind not in {"hackernews", "hf_models", "hf_datasets"}:
        conditions.append(Article.content_hash == values["content_hash"])
    article = await session.scalar(
        select(Article)
        .where(Article.source_id == source.id, or_(*conditions))
        .order_by(Article.collected_at)
        .limit(1)
    )
    if article is None:
        article = Article(source_id=source.id, **values)
        session.add(article)
        await session.flush()
        outcome = "added"
    elif article.content_hash != values["content_hash"] and not item.preserve_existing_content:
        # Do not erase known metadata when an upstream item temporarily omits it.
        for key in ("title", "body", "author", "published_at"):
            if values[key] is not None:
                setattr(article, key, values[key])
        article.content_hash = values["content_hash"]
        article.fingerprint = values["fingerprint"]
        article.title_zh = article.summary_zh = article.category = article.score = None
        article.tags = article.is_ai_related = article.evidence = None
        article.analysis_hash = article.analysis_error = article.retry_at = None
        article.analysis_attempts = 0
        article.updated_at, article.status = now(), "pending"
        outcome = "updated"
    else:
        outcome = "duplicates"
        if article.fingerprint is None:
            article.fingerprint = values["fingerprint"]
        for key in ("author", "published_at"):
            if values[key] is not None and getattr(article, key) != values[key]:
                setattr(article, key, values[key])
    if item.metrics:
        if source.kind == "github_discovery" and item.preserve_existing_content:
            item.metrics["resource"] = {
                **(article.metrics or {}).get("resource", {}),
                **item.metrics.get("resource", {}),
            }
            if item.metrics.get("has_code") is None:
                item.metrics["has_code"] = (article.metrics or {}).get("has_code")
        if (
            source.kind == "hf_models"
            and item.preserve_existing_content
            and item.metrics.get("model")
        ):
            previous = (article.metrics or {}).get("model", {})
            incoming = item.metrics["model"]
            for key in (
                "code_url",
                "paper_url",
                "card_revision",
                "card_observed_at",
                "card_truncated",
                "specifications",
            ):
                if previous.get(key) is not None:
                    incoming[key] = previous[key]
        updated_metrics = {**(article.metrics or {}), **item.metrics}
        if updated_metrics != article.metrics:
            article.updated_at = now()
        article.metrics = updated_metrics
        if source.kind == "hf_models" and item.metrics.get("model"):
            # Hub creation is not a model's announced release date, including legacy records.
            article.published_at = None
    article.metrics = content_metadata(
        article.title,
        article.body,
        source.kind,
        article.metrics,
        article.original_url,
        readme=item.raw.get("readme"),
        reference_body=item.body if not item.preserve_existing_content else None,
    )
    signal = technical_signal(
        article.title, article.body, source.kind, article.metrics, source.trust
    )
    article.technical_score, article.technical_topics = signal.score, signal.topics
    article.technical_reasons, article.technical_eligible = signal.reasons, signal.eligible
    if item.repository:
        await store_repository(session, article, item.repository)
    payload = item.raw or {
        "platform_id": item.platform_id,
        "title": item.title,
        "body": item.body,
        "url": item.url,
        "author": item.author,
        "published_at": item.published_at.isoformat() if item.published_at else None,
    }
    payload_json = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    payload_hash = digest(payload_json)
    exists = await session.scalar(
        select(RawRecord.id).where(
            RawRecord.article_id == article.id, RawRecord.payload_hash == payload_hash
        )
    )
    if not exists:
        session.add(
            RawRecord(
                article_id=article.id, payload_hash=payload_hash, payload=json.loads(payload_json)
            )
        )
    return article, outcome


async def seed_sources(session: AsyncSession) -> None:
    defaults = [
        dict(
            id="arxiv-research",
            name="arXiv 专项工程与科学研究",
            kind="arxiv",
            url="https://export.arxiv.org/api/query",
            trust="preprint",
            interval_minutes=120,
            config={"research_queries": True},
        ),
        dict(
            id="github-discovery",
            name="GitHub AI 项目发现",
            kind="github_discovery",
            url="https://api.github.com/search/repositories",
            trust="maintainer",
            interval_minutes=60,
        ),
        dict(
            id="hf-models",
            name="Hugging Face 模型发现",
            kind="hf_models",
            url="https://huggingface.co/api/models",
            trust="community",
            interval_minutes=60,
        ),
        dict(
            id="hf-datasets",
            name="Hugging Face 技术数据集",
            kind="hf_datasets",
            url="https://huggingface.co/api/datasets",
            trust="community",
            interval_minutes=360,
        ),
        dict(
            id="huggingface",
            name="Hugging Face Blog",
            kind="rss",
            url="https://huggingface.co/blog/feed.xml",
            trust="official",
        ),
        dict(
            id="openai",
            name="OpenAI News",
            kind="rss",
            url="https://openai.com/news/rss.xml",
            trust="official",
            config={"publisher_id": "openai"},
        ),
        dict(
            id="deepmind",
            name="Google DeepMind",
            kind="rss",
            url="https://deepmind.google/blog/rss.xml",
            trust="official",
            config={"publisher_id": "google"},
        ),
        dict(
            id="google-ai",
            name="Google AI 官方动态",
            kind="rss",
            url="https://blog.google/technology/ai/rss/",
            trust="official",
            config={"publisher_id": "google"},
            interval_minutes=120,
        ),
        dict(
            id="nvidia-technical",
            name="NVIDIA 技术博客",
            kind="rss",
            url="https://developer.nvidia.com/blog/feed/",
            trust="official",
            config={"publisher_id": "nvidia"},
            interval_minutes=120,
        ),
        dict(
            id="hackernews",
            name="Hacker News",
            kind="hackernews",
            url="https://hacker-news.firebaseio.com/v0/topstories.json",
            trust="community",
        ),
        dict(
            id="vllm",
            name="vLLM Releases",
            kind="github",
            url="https://api.github.com/repos/vllm-project/vllm/releases",
            config={"repository": "vllm-project/vllm"},
            trust="maintainer",
        ),
        dict(
            id="langchain",
            name="LangChain Releases",
            kind="github",
            url="https://api.github.com/repos/langchain-ai/langchain/releases",
            config={"repository": "langchain-ai/langchain"},
            trust="maintainer",
        ),
        dict(
            id="arxiv-ai",
            name="arXiv · cs.AI",
            kind="arxiv",
            url="https://rss.arxiv.org/rss/cs.AI",
            interval_minutes=360,
            trust="preprint",
        ),
    ]
    defaults.extend(
        dict(
            id=f"arxiv-{category.rsplit('.', 1)[1].lower()}",
            name=f"arXiv · {category}",
            kind="arxiv",
            url=f"https://rss.arxiv.org/rss/{category}",
            interval_minutes=360,
            trust="preprint",
        )
        for category in ["cs.LG", "cs.CL", "cs.CV"]
    )
    for value in defaults:
        existing = await session.get(Source, value["id"])
        if not existing:
            session.add(Source(**value))
        elif existing.url == value["url"] and value.get("config", {}).get("publisher_id"):
            existing.config = {
                "publisher_id": value["config"]["publisher_id"],
                **(existing.config or {}),
            }
        elif existing.id == "hf-models" and existing.name == "Hugging Face 热门模型":
            existing.name = value["name"]
    await session.commit()
