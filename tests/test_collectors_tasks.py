import asyncio
from datetime import timedelta

import pytest
from frontiersignal.collectors import COLLECTORS
from frontiersignal.collectors.base import Collection
from frontiersignal.collectors.github import GitHubCollector
from frontiersignal.collectors.hackernews import HackerNewsCollector
from frontiersignal.config import Settings
from frontiersignal.models import Source, TaskRun, now
from frontiersignal.normalizer import RawItem
from frontiersignal.tasks import TaskManager
from sqlalchemy import select


async def test_hn_independent_item_failure():
    class FakeFetcher:
        settings = Settings(_env_file=None)

        async def json(self, url):
            if any(name in url for name in ["topstories", "beststories", "newstories"]):
                return [1, 2]
            if "item/2" in url:
                raise TimeoutError()
            return {"id": 1, "title": "AI research", "time": 100, "by": "tester"}

    result = await HackerNewsCollector(FakeFetcher()).collect(None)
    assert len(result.items) == 1 and len(result.errors) == 1
    assert result.items[0].url.endswith("id=1")


async def test_github_and_conditional_request():
    class FakeFetcher:
        settings = Settings(_env_file=None)

        async def get(self, url, headers):
            assert "owner/repo/releases" in url
            assert headers["If-None-Match"] == "etag"
            return b"", {}, 304

    source = Source(config={"repository": "owner/repo"}, cursor={"etag": "etag"})
    result = await GitHubCollector(FakeFetcher()).collect(source)
    assert result.items == [] and result.cursor == {"etag": "etag"}
    source.config = {"repository": "../private"}
    with pytest.raises(ValueError):
        await GitHubCollector(FakeFetcher()).collect(source)


async def test_task_isolation_concurrent_submission_and_duplicates(database, monkeypatch):
    db, settings = database
    gate = asyncio.Event()

    class FakeCollector:
        def __init__(self, fetcher):
            pass

        async def collect(self, source):
            await gate.wait()
            if source.id == "broken":
                raise ValueError("Feed unavailable")
            return Collection([RawItem(platform_id="id", title="AI model")])

    monkeypatch.setitem(COLLECTORS, "fake", FakeCollector)
    async with db.sessions() as session:
        session.add_all(
            [
                Source(id=s, name=s, kind="fake", url="https://example.com")
                for s in ["good", "broken"]
            ]
        )
        await session.commit()
    manager = TaskManager(db, settings)
    await manager.start()
    first, repeated, broken = await asyncio.gather(
        manager.submit("good"), manager.submit("good"), manager.submit("broken")
    )
    assert first.id == repeated.id
    gate.set()
    await asyncio.gather(*list(manager.workers))
    again = await manager.submit("good")
    await asyncio.gather(*list(manager.workers))
    async with db.sessions() as session:
        assert (await session.get(TaskRun, first.id)).added == 1
        assert (await session.get(TaskRun, broken.id)).status == "failed"
        assert (await session.get(TaskRun, again.id)).duplicates == 1
    await manager.stop()


async def test_collection_deadline_records_useful_error(database, monkeypatch):
    db, settings = database
    real_timeout = asyncio.timeout
    deadline = None

    def controlled_timeout(seconds):
        nonlocal deadline
        assert seconds == settings.task_timeout
        # Exercise real cancellation at a known phase, independent of database speed.
        deadline = real_timeout(None)
        return deadline

    monkeypatch.setattr("frontiersignal.tasks.asyncio.timeout", controlled_timeout)

    class SlowCollector:
        def __init__(self, fetcher):
            pass

        async def collect(self, source):
            assert deadline is not None
            deadline.reschedule(asyncio.get_running_loop().time())
            await asyncio.Event().wait()

    monkeypatch.setitem(COLLECTORS, "slow", SlowCollector)
    async with db.sessions() as session:
        session.add(Source(id="slow", name="Slow", kind="slow", url="https://example.com"))
        await session.commit()
    manager = TaskManager(db, settings)
    await manager.start()
    try:
        run = await manager.submit("slow")
        await asyncio.wait_for(asyncio.gather(*list(manager.workers)), timeout=15)
        assert deadline is not None and deadline.expired()
        async with db.sessions() as session:
            recorded = await session.get(TaskRun, run.id)
            assert recorded.status == "failed" and "timeout" in recorded.error
            assert recorded.failed == 1 and recorded.finished_at is not None
            assert (await session.get(Source, "slow")).last_status == "failed"
    finally:
        await manager.stop()


async def test_background_collection_does_not_hold_api_request(client, monkeypatch):
    gate = asyncio.Event()

    class SlowCollector:
        def __init__(self, fetcher):
            pass

        async def collect(self, source):
            await gate.wait()
            return Collection([])

    monkeypatch.setitem(COLLECTORS, "rss", SlowCollector)
    response = await asyncio.wait_for(client.post("/api/sources/huggingface/collect"), 1)
    assert response.status_code == 202
    assert (await asyncio.wait_for(client.get("/api/articles"), 1)).status_code == 200
    gate.set()


async def test_recovery_and_disabled_source(database):
    db, settings = database
    async with db.sessions() as session:
        session.add(
            Source(
                id="off",
                name="Off",
                kind="rss",
                url="https://example.com",
                enabled=False,
                last_status="running",
            )
        )
        session.add(TaskRun(status="running", started_at=now() - timedelta(minutes=10)))
        await session.commit()
    manager = TaskManager(db, settings)
    await manager.start()
    async with db.sessions() as session:
        assert (await session.scalar(select(TaskRun))).status == "interrupted"
        assert (await session.get(Source, "off")).last_status == "interrupted"
    with pytest.raises(ValueError):
        await manager.submit("off")
    await manager.stop()
