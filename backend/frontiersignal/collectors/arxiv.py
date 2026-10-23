import asyncio
from urllib.parse import urlencode

from ..discovery_state import record_scan
from ..normalizer import plain_text
from ..technical import technical_signal
from ..topics import CATALOG, selected_topics
from .base import Collection
from .rss import RSSCollector, parse_entries


def research_groups(source):
    return [
        {"id": key, "label": CATALOG[key].label, "topics": [key]} for key in selected_topics(source)
    ]


class ArxivCollector(RSSCollector):
    async def collect(self, source):
        if not (source.config or {}).get("research_queries"):
            return await super().collect(source)
        topics = selected_topics(source)
        tick = (source.cursor or {}).get("research_tick", 0)
        scans = dict((source.cursor or {}).get("scans", {}))
        result = Collection([], advance_on_partial=True)
        steps = min(2, len(topics))
        seen = set()
        for step in range(steps):
            if step:
                await asyncio.sleep(3)
            key = topics[(tick + step) % len(topics)]
            try:
                data, _, _ = await self.fetcher.get(
                    "https://export.arxiv.org/api/query?"
                    + urlencode(
                        {
                            "search_query": CATALOG[key].arxiv_query,
                            "sortBy": "submittedDate",
                            "sortOrder": "descending",
                            "start": 0,
                            "max_results": min(10, self.fetcher.settings.max_items),
                        }
                    )
                )
                items = await asyncio.to_thread(
                    parse_entries, data, self.fetcher.settings.max_items
                )
                for item in items:
                    if "api/errors" in (item.platform_id or ""):
                        raise ValueError("arXiv API 返回查询错误")
                    text = f"{item.title or ''}\n{plain_text(item.body)}"
                    signal = technical_signal(item.title, text, "arxiv", item.metrics)
                    if key not in signal.topics or not signal.eligible:
                        result.filtered += 1
                        continue
                    if item.platform_id in seen:
                        continue
                    seen.add(item.platform_id)
                    item.metrics["query_topics"] = [key]
                    item.metrics["discovery_groups"] = [key]
                    result.items.append(item)
                record_scan(scans, key, label=CATALOG[key].label, topics=[key], count=len(items))
            except Exception as exc:
                error = f"arXiv {CATALOG[key].label}查询失败（{type(exc).__name__}）"
                result.errors.append(error)
                record_scan(scans, key, label=CATALOG[key].label, topics=[key], error=error)
        result.cursor = {"research_tick": tick + steps, "scans": scans}
        return result
