"""Bounded, reviewed public announcement pages; no browser or arbitrary URL entry point."""

import asyncio
import json
from datetime import timedelta
from itertools import zip_longest
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

from bs4 import BeautifulSoup
from protego import Protego

from ..model_info import CREATIVE_FAMILIES, MODEL_FAMILY, annotate_official_model
from ..models import now
from ..normalizer import RawItem
from ..projects import parse_time
from .base import Collection

OFFICIAL_SITES = {
    "anthropic": ("https://www.anthropic.com/sitemap.xml", "/news/", "sitemap"),
    "cohere": ("https://cohere.com/sitemap.xml", "/blog/", "sitemap"),
    "bytedance": ("https://seed.bytedance.com/en/", "/en/blog/", "index"),
    "xai": ("https://x.ai/sitemap.xml", "/news/", "sitemap"),
}
USER_AGENT = "FrontierSignal"


def allowed_article(url, index, prefix):
    parsed, expected = urlsplit(url), urlsplit(index)
    return (
        parsed.scheme == "https"
        and parsed.netloc == expected.netloc
        and parsed.path.startswith(prefix)
        and len(parsed.path) > len(prefix)
        and not parsed.query
        and not parsed.fragment
    )


def index_entries(data, index, prefix, mode):
    if mode == "sitemap":
        root = ElementTree.fromstring(data)
        if root.tag.rsplit("}", 1)[-1] != "urlset":
            raise ValueError("官方站点地图格式发生变化")
        entries = [
            (row.findtext("{*}loc") or "", row.findtext("{*}lastmod"))
            for row in root.findall("{*}url")
        ]
        entries.sort(key=lambda entry: entry[1] or "", reverse=True)
    else:
        soup = BeautifulSoup(data, "html.parser")
        entries = [(urljoin(index, link["href"]), None) for link in soup.select("a[href]")]
    unique = {}
    for url, modified in entries:
        if allowed_article(url, index, prefix):
            unique.setdefault(url, modified)
    if not unique:
        raise ValueError("官方目录未返回可识别的文章链接")
    return list(unique.items())[:300]


def parse_announcement(data, url, source):
    soup = BeautifulSoup(data, "html.parser")
    structured = []
    for node in soup.select('script[type="application/ld+json"]'):
        try:
            value = json.loads(node.get_text())
        except (ValueError, TypeError):
            continue
        values = value if isinstance(value, list) else [value]
        for value in values:
            if isinstance(value, dict):
                structured.extend(value.get("@graph", [value]))
    article = next(
        (
            row
            for row in structured
            if isinstance(row, dict)
            and row.get("@type") in ("Article", "NewsArticle", "BlogPosting")
        ),
        {},
    )
    heading = soup.find("h1")
    title = heading.get_text(" ", strip=True) if heading else article.get("headline")
    if not title:
        raise ValueError("官方页面没有可识别的文章标题")
    published = soup.find("meta", property="article:published_time")
    timestamp = article.get("datePublished") or (published.get("content") if published else None)
    time_node = soup.find("time", datetime=True)
    timestamp = timestamp or (time_node.get("datetime") if time_node else None)
    container = soup.find("article") or soup.find("main")
    if source.config["publisher_id"] == "bytedance":
        date_label = soup.find("p", string="Date")
        date_value = date_label.find_next_sibling("p") if date_label else None
        timestamp = timestamp or (date_value.get_text(strip=True) if date_value else None)
        container = soup.select_one(".markdown-body") or container
    if container:
        for node in container.select("script, style, nav, footer, header, button, aside"):
            node.decompose()
        # Keep link destinations for exact model/paper association; normalizer strips HTML.
        body = str(container)[:80000]
    else:
        description = soup.find("meta", attrs={"name": "description"})
        body = (
            article.get("articleBody")
            or article.get("description")
            or (description.get("content", "") if description else "")
        )
    if not body:
        raise ValueError("官方页面未返回可用正文或摘要")
    date = parse_time(timestamp)
    item = RawItem(
        platform_id=url,
        title=title,
        body=body,
        url=url,
        author=source.name,
        published_at=date,
        raw={
            "url": url,
            "title": title,
            "body": body,
            "datePublished": timestamp,
            "structured_article": article,
        },
        metrics={
            "feed_time_kind": "published" if date else "unknown",
            "publisher_id": source.config["publisher_id"],
            "publication_evidence": "page_metadata" if date else "unavailable",
        },
    )
    annotate_official_model(item, source)
    return item


class OfficialCollector:
    def __init__(self, fetcher):
        self.fetcher = fetcher

    async def collect(self, source):
        publisher = (source.config or {}).get("publisher_id")
        if publisher not in OFFICIAL_SITES:
            raise ValueError("尚未审核的官方发布来源")
        index, prefix, mode = OFFICIAL_SITES[publisher]
        if source.url != index or source.trust != "official":
            raise ValueError("官方来源配置与已审核入口不一致")
        origin = f"https://{urlsplit(index).netloc}"
        data, _, _ = await self.fetcher.get(origin + "/robots.txt")
        robots = Protego.parse(data.decode("utf-8"))
        if not robots.can_fetch(index, USER_AGENT):
            raise ValueError("官方站点禁止访问该目录")
        data, _, _ = await self.fetcher.get(index)
        entries = await asyncio.to_thread(index_entries, data, index, prefix, mode)
        previous = (source.cursor or {}).get("pages", {})
        pages = {url: previous[url] for url, _ in entries if url in previous}
        result = Collection([], advance_on_partial=True)
        budget = min(4, self.fetcher.settings.max_items)
        due = []
        for url, modified in entries:
            cached = pages.get(url, {})
            checked = parse_time(cached.get("checked_at"))
            if (
                checked
                and cached.get("modified") == modified
                and checked > now() - timedelta(days=7)
            ):
                continue
            if not robots.can_fetch(url, USER_AGENT):
                continue
            due.append((url, modified))

        # Reserve slots for explicit model-family candidates without dropping ordinary research.
        def model_candidate(entry):
            path = urlsplit(entry[0]).path
            return bool(
                MODEL_FAMILY.search(path)
                or any(pattern.search(path) for pattern in CREATIVE_FAMILIES.values())
            )

        releases = [entry for entry in due if model_candidate(entry)]
        research = [entry for entry in due if not model_candidate(entry)]
        ordered = [entry for pair in zip_longest(releases, research) for entry in pair if entry]
        for url, modified in ordered:
            if budget <= 0:
                break
            budget -= 1
            try:
                data, _, _ = await self.fetcher.get(url)
                item = await asyncio.to_thread(parse_announcement, data, url, source)
                result.items.append(item)
                pages[url] = {"modified": modified, "checked_at": now().isoformat()}
            except Exception as exc:
                result.errors.append(f"官方文章读取失败 {url}（{type(exc).__name__}）")
        result.cursor = {"pages": pages}
        return result
