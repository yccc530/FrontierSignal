"""Exact arXiv identity lookup; missing counts are never treated as zero."""

import asyncio
import re
from datetime import timedelta
from urllib.parse import quote

from .models import now
from .projects import parse_time

ARXIV_ID = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf)/|arxiv[:.])([a-z-]+(?:\.[A-Z]{2})?/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?",
    re.I,
)


def arxiv_id(value):
    match = ARXIV_ID.search(str(value or ""))
    return match.group(1).lower() if match else None


async def lookup_citations(fetcher, identifier):
    at = now().isoformat()
    url = "https://api.openalex.org/works/" + quote(
        f"https://doi.org/10.48550/arXiv.{identifier}", safe="/:."
    )
    try:
        async with asyncio.timeout(12):
            payload = await fetcher.json(url)
        identities = [payload.get("doi"), *(payload.get("ids") or {}).values()]
        for location in payload.get("locations") or []:
            identities.extend([location.get("landing_page_url"), location.get("pdf_url")])
        if not any(arxiv_id(value) == identifier for value in identities):
            raise ValueError("引用记录未匹配原始 arXiv ID")
        count = payload.get("cited_by_count")
        if type(count) is not int or count < 0:
            raise ValueError("缺少有效引用数量")
        work_url = payload.get("id")
        if not isinstance(work_url, str) or not re.fullmatch(
            r"https://openalex.org/W\d+", work_url
        ):
            raise ValueError("缺少有效的引用来源")
        return {
            "count": count,
            "provider": "OpenAlex",
            "url": work_url,
            "arxiv_id": identifier,
            "observed_at": at,
            "checked_at": at,
            "status": "available",
        }
    except Exception as exc:
        return {
            "count": None,
            "provider": "OpenAlex",
            "arxiv_id": identifier,
            "checked_at": at,
            "status": "unavailable",
            "error": f"引用服务暂不可用或未收录（{type(exc).__name__}）",
        }


def merge_citations(previous, incoming):
    if incoming.get("count") is None and previous.get("count") is not None:
        return {
            **previous,
            "checked_at": incoming["checked_at"],
            "status": "stale",
            "error": incoming.get("error"),
        }
    return incoming


async def enrich_papers(collection, source, fetcher):
    cache = dict((source.cursor or {}).get("citations", {}))
    budget = getattr(fetcher.settings, "citation_checks", 0)
    for item in collection.items:
        identifier = arxiv_id(item.url) or arxiv_id(item.platform_id)
        if not identifier:
            continue
        previous = cache.get(identifier, {})
        checked = parse_time(previous.get("checked_at"))
        if budget and (not checked or checked < now() - timedelta(days=1)):
            budget -= 1
            incoming = await lookup_citations(fetcher, identifier)
            cache[identifier] = merge_citations(previous, incoming)
        if identifier in cache:
            item.metrics["citations"] = cache[identifier]
    # Keep a bounded cache across RSS conditional requests and query rotation.
    collection.cursor["citations"] = dict(
        sorted(cache.items(), key=lambda row: row[1].get("checked_at", ""), reverse=True)[:300]
    )
    return collection
