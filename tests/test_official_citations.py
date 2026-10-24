import asyncio
from datetime import timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from frontiersignal.citations import arxiv_id, enrich_papers, lookup_citations, merge_citations
from frontiersignal.collectors import COLLECTORS
from frontiersignal.collectors.base import Collection
from frontiersignal.collectors.huggingface import HuggingFaceCollector
from frontiersignal.collectors.official import OfficialCollector, index_entries, parse_announcement
from frontiersignal.config import Settings
from frontiersignal.models import ArticleLink, Source, TaskRun, now
from frontiersignal.normalizer import RawItem
from frontiersignal.publishers import publisher_for_author
from frontiersignal.recommendation_state import revision_hash
from frontiersignal.similarity import link_related
from frontiersignal.storage import ingest
from frontiersignal.tasks import TaskManager
from sqlalchemy import select


async def test_official_ingestion_failure_remains_retryable(database, monkeypatch):
    db, settings = database
    url = "https://www.anthropic.com/news/test"

    class Collector:
        def __init__(self, fetcher):
            pass

        async def collect(self, source):
            return Collection(
                [RawItem(title="AI model", url=url)],
                cursor={"pages": {url: {"checked_at": now().isoformat()}}},
                advance_on_partial=True,
            )

    async def reject(session, source, item):
        raise ValueError("Invalid original")

    monkeypatch.setitem(COLLECTORS, "official", Collector)
    monkeypatch.setattr("frontiersignal.tasks.ingest", reject)
    async with db.sessions() as session:
        session.add(Source(id="news", name="News", kind="official", url=url))
        await session.commit()
    manager = TaskManager(db, settings)
    await manager.start()
    try:
        run = await manager.submit("news")
        await asyncio.gather(*list(manager.workers))
        async with db.sessions() as session:
            assert (await session.get(TaskRun, run.id)).failed == 1
            assert url not in (await session.get(Source, "news")).cursor["pages"]
    finally:
        await manager.stop()


async def test_targeted_publisher_keeps_rotation_and_has_bounded_queries():
    class Fetcher:
        settings = Settings(hf_card_checks=0, _env_file=None)

        def __init__(self):
            self.calls = []

        async def json(self, url):
            params = parse_qs(urlsplit(url).query)
            self.calls.append(params)
            assert params["author"] == ["moonshotai"]
            return [{"id": "moonshotai/Kimi-K2", "pipeline_tag": "text-generation"}]

    source = Source(
        kind="hf_models",
        config={},
        cursor={"model_tick": 42, "scans": {"publisher:meta": {"status": "success"}}},
    )
    fetcher = Fetcher()
    collector = HuggingFaceCollector(fetcher)
    collector.publisher_id = "kimi"
    result = await collector.collect(source)
    assert len(fetcher.calls) == 2 and len(result.items) == 1 and not result.errors
    assert result.cursor["model_tick"] == 42
    assert result.cursor["scans"]["publisher:meta"]["status"] == "success"
    assert result.items[0].metrics["model"]["publisher_id"] == "kimi"


def test_publisher_identity_and_reviewed_accounts():
    for account, publisher in {
        "moonshotai": "kimi",
        "MiniMaxAI": "minimax",
        "stepfun-ai": "stepfun",
        "baidu": "baidu",
        "PaddlePaddle": "baidu",
        "internlm": "intern",
        "OpenGVLab": "intern",
        "nvidia": "nvidia",
        "ByteDance-Seed": "bytedance",
        "CohereLabs": "cohere",
        "amazon": "amazon",
        "xai-org": "xai",
    }.items():
        assert publisher_for_author(account)[0] == publisher
    assert publisher_for_author("hunyuanvideo-community") == (None, None)
    assert publisher_for_author("MiniMaxAI-fan") == (None, None)


def announcement_html(title="Introducing Claude Opus 4", date="2026-10-20"):
    return f'''<html><head><meta property="article:published_time" content="{date}"></head>
    <body><article><h1>{title}</h1><p>Model inference benchmark and training architecture.</p>
    <a href="https://arxiv.org/abs/1706.03762">Paper</a></article></body></html>'''.encode()


def test_official_dates_and_closed_model_announcements():
    source = Source(
        name="Anthropic",
        trust="official",
        url="https://www.anthropic.com/sitemap.xml",
        config={"publisher_id": "anthropic"},
    )
    item = parse_announcement(announcement_html(), "https://www.anthropic.com/news/opus", source)
    assert item.metrics["model"]["publisher_id"] == "anthropic"
    assert item.metrics["model"]["weights_url"] is None
    assert item.published_at.day == 20
    missing = parse_announcement(announcement_html(date=""), item.url, source)
    assert missing.published_at is None
    regular = parse_announcement(
        announcement_html(title="Inside inference architecture"), item.url, source
    )
    assert regular.metrics["publisher_id"] == "anthropic" and "model" not in regular.metrics
    vault = parse_announcement(
        announcement_html(title="Introducing Cohere Model Vault"), item.url, source
    )
    assert "model" not in vault.metrics
    bare = parse_announcement(
        announcement_html(title="Claude 3.7 Sonnet").replace(
            b"Model inference", b"Today we are announcing Claude 3.7 Sonnet. Model inference"
        ),
        item.url,
        source,
    )
    assert bare.metrics["kind"] == "model_release"
    aws = Source(
        name="AWS",
        trust="official",
        url="https://aws.amazon.com/blogs/machine-learning/feed/",
        config={"publisher_id": "amazon"},
    )
    hosted = parse_announcement(
        announcement_html(title="Introducing Claude Sonnet 4 on Amazon Bedrock"),
        "https://aws.amazon.com/blogs/machine-learning/claude",
        aws,
    )
    assert hosted.metrics["publisher_id"] == "amazon" and "model" not in hosted.metrics
    entries = index_entries(
        b"""<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://www.anthropic.com/news/opus</loc><lastmod>2026-10-22</lastmod></url>
    <url><loc>https://evil.test/news/opus</loc></url>
    <url><loc>https://www.anthropic.com/careers/opus</loc></url></urlset>""",
        source.url,
        "/news/",
        "sitemap",
    )
    assert entries == [(item.url, "2026-10-22")]


async def test_official_partial_failure_and_cached_pages():
    class Fetcher:
        settings = Settings(_env_file=None)

        def __init__(self):
            self.calls = []

        async def get(self, url):
            self.calls.append(url)
            if url.endswith("robots.txt"):
                return b"User-agent: *\nAllow: /\nDisallow: /news/blocked", {}, 200
            if url.endswith("sitemap.xml"):
                return (
                    (
                        "<urlset>"
                        + "".join(
                            f"<url><loc>https://www.anthropic.com/news/{slug}</loc></url>"
                            for slug in ["ok", "bad", "blocked"]
                        )
                        + "</urlset>"
                    ).encode(),
                    {},
                    200,
                )
            if url.endswith("bad"):
                raise ValueError("private detail")
            assert not url.endswith("blocked")
            return announcement_html(), {}, 200

    source = Source(
        name="Anthropic",
        trust="official",
        url="https://www.anthropic.com/sitemap.xml",
        config={"publisher_id": "anthropic"},
        cursor={},
    )
    fetcher = Fetcher()
    first = await OfficialCollector(fetcher).collect(source)
    assert len(first.items) == 1 and len(first.errors) == 1 and first.advance_on_partial
    assert "private detail" not in first.errors[0]
    source.cursor = first.cursor
    fetcher.calls.clear()
    second = await OfficialCollector(fetcher).collect(source)
    assert not second.items and not any(url.endswith("/ok") for url in fetcher.calls)


async def test_citations_exact_identity_unknown_cache_and_refresh():
    class Fetcher:
        settings = SimpleNamespace(citation_checks=2)
        calls = 0
        mismatch = False

        async def json(self, url):
            self.calls += 1
            return {
                "id": "https://openalex.org/W123",
                "cited_by_count": 0,
                "locations": [
                    {
                        "landing_page_url": "https://arxiv.org/abs/"
                        + ("9999.00001" if self.mismatch else "1706.03762v5")
                    }
                ],
            }

    fetcher = Fetcher()
    source = Source(cursor={})

    def batch():
        return Collection([RawItem(url="https://arxiv.org/abs/1706.03762v5")])

    first = await enrich_papers(batch(), source, fetcher)
    assert first.items[0].metrics["citations"]["count"] == 0
    source.cursor = first.cursor
    await enrich_papers(batch(), source, fetcher)
    assert fetcher.calls == 1
    fetcher.mismatch = True
    failed = await lookup_citations(fetcher, "1706.03762")
    assert failed["count"] is None and failed["status"] == "unavailable"
    stale = merge_citations(first.items[0].metrics["citations"], failed)
    assert stale["count"] == 0 and stale["status"] == "stale"
    assert arxiv_id("https://doi.org/10.48550/arXiv.1706.03762") == "1706.03762"


async def test_sorting_scope_nulls_pagination_and_official_filter(client, database):
    db, _ = database
    async with db.sessions() as session:
        source = await session.get(Source, "arxiv-ai")
        ids = []
        for index, count in enumerate([None, 0, 25, 25]):
            item = RawItem(
                platform_id=str(index),
                url="https://arxiv.org/abs/1706.03762" if index == 0 else None,
                title=f"Neural AI paper {index}",
                body=f"Reproducible language model training research {index}",
                published_at=now() - timedelta(days=index),
                metrics={"citations": {"count": count}},
            )
            article, _ = await ingest(session, source, item)
            ids.append(article.id)
        official = await session.get(Source, "anthropic-news")
        article, _ = await ingest(
            session,
            official,
            RawItem(
                title="AI inference training",
                body='<p>Technical report</p><a href="https://arxiv.org/abs/1706.03762">Paper</a>',
                metrics={"publisher_id": "anthropic"},
            ),
        )
        await link_related(session, article)
        assert (await session.scalar(select(ArticleLink))).method == "paper_reference"
        original_revision = revision_hash(article)
        article.metrics = {**article.metrics, "citations": {"count": 123}}
        assert revision_hash(article) == original_revision
        await session.commit()
    response = (await client.get("/api/articles?sort=citations&page_size=2")).json()
    assert response["total"] == 4
    assert [item["id"] for item in response["items"]] == [ids[2], ids[3]]
    second = (await client.get("/api/articles?sort=citations&page_size=2&page=2")).json()
    assert [item["id"] for item in second["items"]] == [ids[1], ids[0]]
    oldest = (await client.get("/api/articles?source=arxiv-ai&sort=oldest")).json()
    assert oldest["items"][0]["id"] == ids[3]
    publisher = (await client.get("/api/articles?publisher=anthropic")).json()
    assert publisher["total"] == 1
    assert (await client.get("/api/articles?sort=invalid")).status_code == 422
    sources = (await client.get("/api/sources")).json()
    assert not next(row for row in sources if row["id"] == "xai-news")["enabled"]


async def test_model_time_sort_uses_source_update_not_recent_import(client, database):
    db, _ = database
    async with db.sessions() as session:
        source = await session.get(Source, "hf-models")
        for label, updated, collected in [
            ("old", "2020-01-01T08:00:00+08:00", now()),
            ("new", "2026-10-20T00:00:00Z", now() - timedelta(days=1)),
        ]:
            article, _ = await ingest(
                session,
                source,
                RawItem(
                    platform_id=label,
                    title=label,
                    body="AI model training",
                    metrics={
                        "kind": "model",
                        "model": {"hub_updated_at": updated, "topics": ["llm"]},
                    },
                ),
            )
            article.collected_at = collected
        await session.commit()
    newest = (await client.get("/api/articles?source=hf-models&sort=published")).json()
    assert [row["title"] for row in newest["items"]] == ["new", "old"]
    assert newest["items"][0]["published_at"] is None
    assert newest["items"][0]["source_updated_at"] is not None
    imported = (await client.get("/api/articles?source=hf-models&sort=collected")).json()
    assert [row["title"] for row in imported["items"]] == ["old", "new"]
    window = (await client.get("/api/articles?source=hf-models&after=2026-01-01T00:00:00Z")).json()
    assert window["total"] == 1
