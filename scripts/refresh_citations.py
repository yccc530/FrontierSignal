"""Refresh a bounded set of existing arXiv records without re-running AI analysis."""

import argparse
import asyncio
from datetime import timedelta

from frontiersignal.citations import arxiv_id, lookup_citations, merge_citations
from frontiersignal.config import settings
from frontiersignal.db import Database
from frontiersignal.models import Article, now
from frontiersignal.network import Fetcher
from frontiersignal.projects import parse_time
from sqlalchemy import select


async def refresh(limit):
    db, fetcher = Database(settings), Fetcher(settings)
    success = unavailable = 0
    try:
        async with db.sessions() as session:
            rows = (
                await session.scalars(
                    select(Article)
                    .where(Article.source.has(kind="arxiv"))
                    .order_by(Article.collected_at.desc())
                    .limit(1000)
                )
            ).all()
            for article in rows:
                if success + unavailable >= limit:
                    break
                previous = (article.metrics or {}).get("citations", {})
                checked = parse_time(previous.get("checked_at"))
                if checked and checked > now() - timedelta(days=1):
                    continue
                identifier = arxiv_id(article.original_url) or arxiv_id(article.platform_id)
                if not identifier:
                    continue
                result = await lookup_citations(fetcher, identifier)
                # Reload after the network call to preserve concurrent collection metadata.
                await session.refresh(article)
                previous = (article.metrics or {}).get("citations", {})
                article.metrics = {
                    **(article.metrics or {}),
                    "citations": merge_citations(previous, result),
                }
                await session.commit()
                if result["count"] is None:
                    unavailable += 1
                else:
                    success += 1
                print(identifier, result["status"], result["count"], flush=True)
        print(f"Updated: {success}; unavailable: {unavailable}; limit: {limit}")
    finally:
        await db.engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.limit <= 50:
        parser.error("--limit must be 1..50")
    asyncio.run(refresh(args.limit))
