"""Rebuild local rule signals from saved originals without LLM or external requests."""

import asyncio

from frontiersignal.config import settings
from frontiersignal.db import Database
from frontiersignal.models import Article, RawRecord, Repository
from frontiersignal.technical import technical_signal
from sqlalchemy import select


async def main():
    db = Database(settings)
    count = eligible = 0
    try:
        async with db.sessions() as session:
            rows = (await session.scalars(select(Article).order_by(Article.id))).all()
            for article in rows:
                metrics = dict(article.metrics or {})
                raw = await session.scalar(
                    select(RawRecord)
                    .where(RawRecord.article_id == article.id)
                    .order_by(RawRecord.collected_at.desc())
                    .limit(1)
                )
                payload = raw.payload if raw else {}
                if article.source.kind == "hackernews" and payload.get("id"):
                    discussion = f"https://news.ycombinator.com/item?id={payload['id']}"
                    metrics = {
                        **metrics,
                        "kind": "discussion",
                        "points": payload.get("score"),
                        "comments_count": payload.get("descendants"),
                        "discussion_url": discussion,
                        "observed_at": raw.collected_at.isoformat(),
                        "comments_sample": payload.get("comment_sample", []),
                    }
                    article.canonical_url = discussion
                elif article.source.kind == "arxiv":
                    metrics = {
                        **metrics,
                        "categories": [
                            tag.get("term") for tag in payload.get("tags", []) if tag.get("term")
                        ],
                        "authors": [
                            author.get("name")
                            for author in payload.get("authors", [])
                            if author.get("name")
                        ],
                    }
                elif article.source.kind == "github":
                    metrics = {
                        **metrics,
                        "kind": "release",
                        "repository": article.source.config.get("repository"),
                    }
                article.metrics = metrics
                signal = technical_signal(
                    article.title, article.body, article.source.kind, metrics, article.source.trust
                )
                article.technical_score, article.technical_eligible = signal.score, signal.eligible
                article.technical_topics, article.technical_reasons = signal.topics, signal.reasons
                if metrics.get("kind") == "repository":
                    repository = await session.scalar(
                        select(Repository).where(Repository.article_id == article.id)
                    )
                    if repository:
                        repository.tracked = (
                            signal.eligible
                            and not repository.archived
                            and not metrics.get("fork", False)
                        )
                count += 1
                eligible += int(signal.eligible)
            await session.commit()
        print({"processed": count, "technical_eligible": eligible, "llm_requests": 0})
    finally:
        await db.engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
