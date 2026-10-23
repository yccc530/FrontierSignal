import pytest
from frontiersignal.collectors.rss import parse_entries
from frontiersignal.models import Article, RawRecord, Source
from frontiersignal.network import validate_feed_url
from frontiersignal.normalizer import RawItem, canonical_url, normalize
from frontiersignal.storage import ingest
from sqlalchemy import func, select


def test_url_normalization_keeps_meaning():
    assert (
        canonical_url("https://Example.COM:443/A/?a=2&utm_source=rss#x")
        == "https://example.com/A/?a=2"
    )
    assert canonical_url("https://example.com?a=2&a=1") == "https://example.com/?a=2&a=1"
    assert canonical_url("javascript:alert(1)") is None
    assert canonical_url("https://user:pass@example.com") is None


def test_missing_fields_and_html():
    value = normalize(RawItem(platform_id="id", body="<p>Text</p><script>bad()</script>"))
    assert value["title"] is None and value["published_at"] is None
    assert value["body"] == "Text"
    with pytest.raises(ValueError):
        normalize(RawItem())


def test_feed_parsing():
    data = b'<feed xmlns="http://www.w3.org/2005/Atom"><title>Fixture</title><entry><id>id1</id><title>Test</title><summary>short</summary><content>long body</content></entry></feed>'
    item = parse_entries(data, 10)[0]
    assert item.body == "long body" and item.published_at is None
    with pytest.raises(ValueError):
        parse_entries(b"<html>Not RSS</html>", 10)


def test_url_fetch_boundary():
    for url in (
        "http://example.com/feed",
        "https://127.0.0.1/",
        "https://example.com:444/feed",
        "https://example.com@127.0.0.1/feed",
    ):
        with pytest.raises(ValueError):
            validate_feed_url(url, {"example.com"})


async def test_dedup_versions_and_independent_sources(database):
    db, _ = database
    async with db.sessions() as session:
        first = Source(id="a", name="A", kind="rss", url="https://a.example/rss")
        second = Source(id="b", name="B", kind="rss", url="https://b.example/rss")
        session.add_all([first, second])
        await session.flush()
        item = RawItem(
            platform_id="42", title="Model release", body="original", url="https://example.com/post"
        )
        row, status = await ingest(session, first, item)
        assert status == "added"
        _, status = await ingest(session, first, item)
        assert status == "duplicates"
        row.title_zh, row.summary_zh, row.status = "模型发布", "原文的中文摘要", "analyzed"
        _, status = await ingest(session, first, item)
        assert status == "duplicates" and row.title_zh == "模型发布"
        item.body = "updated"
        _, status = await ingest(session, first, item)
        assert status == "updated"
        assert row.title_zh is None and row.summary_zh is None and row.status == "pending"
        await ingest(session, second, item)
        await session.commit()
        assert await session.scalar(select(func.count()).select_from(Article)) == 2
        assert (
            await session.scalar(
                select(func.count()).select_from(RawRecord).where(RawRecord.article_id == row.id)
            )
            == 2
        )


async def test_api_and_management_boundary(client):
    assert (await client.get("/api/health")).status_code == 200
    data = (await client.get("/api/articles")).json()
    assert data["items"] == [] and data["total"] == 0
    assert (await client.get("/api/articles?page=0")).status_code == 422
    assert (await client.get("/api/articles/absent")).status_code == 404
    assert (
        await client.get("/api/health", headers={"Origin": "https://evil.example"})
    ).status_code == 403
    assert (
        await client.post("/api/sources/huggingface/collect", headers={"X-FrontierSignal": ""})
    ).status_code == 403
