"""Rebuild local rule signals from saved originals without LLM or external requests."""

import argparse
import asyncio
from copy import deepcopy

from frontiersignal.config import settings
from frontiersignal.content_info import content_metadata
from frontiersignal.db import Database
from frontiersignal.model_info import annotate_official_model, attach_model_card, model_metadata
from frontiersignal.models import Article, RawRecord, Repository
from frontiersignal.normalizer import RawItem
from frontiersignal.publishers import PUBLISHERS, publisher_authors
from frontiersignal.similarity import rebuild_explicit_links
from frontiersignal.technical import technical_signal
from sqlalchemy import false, func, or_, select


async def main(apply=False, limit=500, after_id="", link_references=False, publisher=None):
    db = Database(settings)
    count = eligible = changed = 0
    last_id = None
    try:
        async with db.sessions(autoflush=False) as session:
            query = select(Article).where(Article.id > after_id)
            if publisher:
                authors = publisher_authors(PUBLISHERS[publisher])
                query = query.where(
                    Article.source.has(kind="hf_models"),
                    or_(
                        false(),
                        *(
                            func.lower(Article.platform_id).startswith(
                                f"{author.casefold()}/", autoescape=True
                            )
                            for author in authors
                        ),
                    ),
                )
            rows = (await session.scalars(query.order_by(Article.id).limit(limit))).all()
            for article in rows:
                before = (
                    article.technical_topics,
                    article.technical_score,
                    article.technical_eligible,
                    deepcopy(article.metrics),
                    article.published_at,
                    article.canonical_url,
                )
                metrics = dict(article.metrics or {})
                raw = await session.scalar(
                    select(RawRecord)
                    .where(RawRecord.article_id == article.id)
                    .order_by(RawRecord.collected_at.desc())
                    .limit(1)
                )
                payload = raw.payload if raw else {}
                if article.source.kind == "hf_models":
                    original = payload.get("api", payload)
                    if original.get("id"):
                        previous = metrics.get("model") or {}
                        model = model_metadata(original)
                        for key in (
                            "card_status",
                            "card_revision",
                            "card_observed_at",
                            "card_truncated",
                            "code_url",
                            "paper_url",
                            "specifications",
                        ):
                            if key in previous:
                                model[key] = previous[key]
                        if model.get("card_revision") and model.get("card_status") in {
                            "available",
                            "cached",
                        }:
                            attach_model_card(model, payload.get("model_card") or article.body)
                        metrics["model"] = model
                        metrics["kind"] = "model"
                        article.published_at = None
                elif article.source.kind == "rss" and article.source.trust == "official":
                    metrics["feed_time_kind"] = (
                        "published"
                        if payload.get("published_parsed")
                        else "updated"
                        if payload.get("updated_parsed")
                        else "unknown"
                    )
                    content = payload.get("content") or []
                    body = (
                        (content[0].get("value", "") if content else "")
                        or payload.get("summary")
                        or article.body
                    )
                    item = RawItem(
                        title=article.title,
                        body=body,
                        published_at=article.published_at,
                        metrics=metrics,
                        url=article.original_url,
                    )
                    annotate_official_model(item, article.source)
                    metrics = item.metrics
                elif article.source.kind == "hackernews" and payload.get("id"):
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
                metrics = content_metadata(
                    article.title,
                    article.body,
                    article.source.kind,
                    metrics,
                    article.original_url,
                    readme=payload.get("readme"),
                )
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
                changed += before != (
                    signal.topics,
                    signal.score,
                    signal.eligible,
                    article.metrics,
                    article.published_at,
                    article.canonical_url,
                )
                last_id = article.id
            links = None
            if link_references:
                await session.flush()
                links = await rebuild_explicit_links(session, rows)
            if apply:
                await session.commit()
            else:
                await session.rollback()
        print(
            {
                "mode": "applied" if apply else "preview",
                "processed": count,
                "changed": changed,
                "technical_eligible": eligible,
                "llm_requests": 0,
                "publisher": publisher,
                "explicit_links": links,
                "next_after_id": last_id if count == limit else None,
            }
        )
    finally:
        await db.engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="Persist changes; the default only previews"
    )
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--after-id", default="")
    parser.add_argument(
        "--publisher",
        choices=list(PUBLISHERS),
        help="Only saved Hub originals owned by this publisher",
    )
    parser.add_argument(
        "--link-references",
        action="store_true",
        help="Also rebuild bounded explicit model/paper/code/dataset references",
    )
    args = parser.parse_args()
    if not 1 <= args.limit <= 5000:
        parser.error("--limit must be 1..5000")
    asyncio.run(main(args.apply, args.limit, args.after_id, args.link_references, args.publisher))
