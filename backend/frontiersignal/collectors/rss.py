# Portions adapted from AI News Brief, Copyright (c) 2026 frankzch (MIT).
# See THIRD_PARTY_NOTICES.md. Network and persistence are intentionally separate.
import asyncio
from calendar import timegm
from datetime import UTC, datetime

import feedparser

from ..model_info import annotate_official_model
from ..models import Source
from ..network import Fetcher
from ..normalizer import RawItem
from .base import Collection


def parse_entries(data: bytes, limit: int) -> list[RawItem]:
    feed = feedparser.parse(data)
    if not feed.version or (feed.bozo and not feed.entries):
        raise ValueError("Source did not return a usable RSS/Atom feed")
    items = []
    for entry in feed.entries[:limit]:
        parsed_date = entry.get("published_parsed") or entry.get("updated_parsed")
        try:
            published = datetime.fromtimestamp(timegm(parsed_date), UTC) if parsed_date else None
        except (OverflowError, ValueError):
            published = None
        content = entry.get("content") or []
        body = (
            (content[0].get("value", "") if content else "")
            or entry.get("summary", "")
            or entry.get("description", "")
        )
        items.append(
            RawItem(
                platform_id=entry.get("id"),
                title=entry.get("title"),
                body=body,
                url=entry.get("link"),
                author=entry.get("author"),
                published_at=published,
                raw=dict(entry),
                metrics={
                    "feed_time_kind": "published"
                    if entry.get("published_parsed")
                    else "updated"
                    if entry.get("updated_parsed")
                    else "unknown",
                    "authors": [
                        author.get("name")
                        for author in entry.get("authors", [])
                        if author.get("name")
                    ],
                    "categories": [
                        tag.get("term") for tag in entry.get("tags", []) if tag.get("term")
                    ],
                },
            )
        )
    return items


class RSSCollector:
    def __init__(self, fetcher: Fetcher):
        self.fetcher = fetcher

    async def collect(self, source: Source) -> Collection:
        headers = {}
        if source.cursor.get("etag"):
            headers["If-None-Match"] = source.cursor["etag"]
        if source.cursor.get("modified"):
            headers["If-Modified-Since"] = source.cursor["modified"]
        data, response_headers, status = await self.fetcher.get(source.url, headers)
        if status == 304:
            return Collection([], source.cursor)
        # Feed parser is bounded by the network response limit.
        items = await asyncio.to_thread(parse_entries, data, self.fetcher.settings.max_items)
        for item in items:
            annotate_official_model(item, source)
        lowered = {k.lower(): v for k, v in response_headers.items()}
        return Collection(
            items, {"etag": lowered.get("etag"), "modified": lowered.get("last-modified")}
        )
