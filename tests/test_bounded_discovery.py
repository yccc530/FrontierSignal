import asyncio
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from frontiersignal import backfill, network
from frontiersignal.analysis import AnalysisPipeline
from frontiersignal.backfill import BackfillRequest, backfill_pages
from frontiersignal.collectors import github_discovery
from frontiersignal.collectors.github_discovery import (
    GitHubDiscoveryCollector,
    infrastructure_search,
)
from frontiersignal.config import Settings
from frontiersignal.coverage_audit import coverage_audit
from frontiersignal.discovery_budget import load_discovery_budget
from frontiersignal.github_catalog import fixed_repository, organization_identity
from frontiersignal.models import Article, RawRecord, Source, TaskRun
from frontiersignal.network import Fetcher, FetchError
from frontiersignal.normalizer import RawItem
from frontiersignal.storage import ingest
from frontiersignal.tasks import TaskManager
from pydantic import SecretStr, ValidationError
from sqlalchemy import func, select

AT = datetime(2026, 11, 5, 12, tzinfo=UTC)
WINDOW = {"start_date": "2026-10-31", "end_date": "2026-11-04"}


@pytest.fixture(autouse=True)
def fixed_backfill_date(monkeypatch):
    monkeypatch.setattr(backfill, "now", lambda: AT)
    monkeypatch.setattr(github_discovery, "now", lambda: AT)


def atom(*identifiers):
    entries = "".join(
        f"<entry><id>http://arxiv.org/abs/2610.{identifier:05d}v1</id>"
        f"<title>{'LLM inference benchmark' if identifier % 2 else 'Classical botany'}</title>"
        "<summary>A source abstract with reproducible methods and original observations.</summary>"
        "<published>2026-11-02T12:00:00Z</published>"
        f'<link href="https://arxiv.org/abs/2610.{identifier:05d}v1"/>'
        "<author><name>Fixture Author</name></author></entry>"
        for identifier in identifiers
    )
    return (
        f'<feed xmlns="http://www.w3.org/2005/Atom"><title>Fixture</title>{entries}</feed>'.encode()
    )


class ArxivFetcher:
    settings = Settings(_env_file=None)

    def __init__(self, fail_second=False):
        self.calls = []
        self.fail_second = fail_second

    async def get(self, url):
        query = parse_qs(urlsplit(url).query)
        self.calls.append(query)
        if self.fail_second and int(query["start"][0]):
            raise FetchError("fixture page failure", 503)
        start = int(query["start"][0])
        count = int(query["max_results"][0])
        return atom(*range(start + 1, start + count + 1)), {}, 200


@pytest.mark.parametrize(
    "values",
    [
        {"start_date": "2026-11-05", "end_date": "2026-11-04"},
        {"start_date": "2026-10-01", "end_date": "2026-11-04"},
        {"start_date": "2026-10-31", "end_date": "2026-11-06"},
        {**WINDOW, "max_pages": 6},
        {**WINDOW, "start_page": 5, "max_pages": 2},
        {**WINDOW, "per_page": 51},
        {**WINDOW, "topics": ["llm", "llm"]},
    ],
)
def test_invalid_backfill_windows_and_budgets_are_rejected(values):
    with pytest.raises(ValidationError):
        BackfillRequest(**values)


async def test_arxiv_backfill_has_inclusive_utc_window_and_finite_pages():
    source = Source(
        kind="arxiv", url="https://rss.arxiv.org/rss/cs.AI", config={}, cursor={"etag": "keep"}
    )
    fetcher = ArxivFetcher()
    pages = [
        page
        async for page in backfill_pages(
            fetcher, source, BackfillRequest(**WINDOW, max_pages=2, per_page=2)
        )
    ]
    assert [int(query["start"][0]) for query in fetcher.calls] == [0, 2]
    assert all(
        query["sortBy"] == ["submittedDate"] and query["sortOrder"] == ["descending"]
        for query in fetcher.calls
    )
    assert "submittedDate:[202610310000 TO 202611042359]" in fetcher.calls[0]["search_query"][0]
    assert len(pages) == 2 and sum(len(collection.items) for collection, _ in pages) == 4
    assert all(item.defer_analysis for collection, _ in pages for item in collection.items)
    assert source.cursor == {"etag": "keep"}


async def test_backfill_can_retry_only_the_failed_page_without_restarting_the_window():
    source = Source(kind="arxiv", url="https://rss.arxiv.org/rss/cs.AI", config={}, cursor={})
    fetcher = ArxivFetcher()
    pages = [
        page
        async for page in backfill_pages(
            fetcher, source, BackfillRequest(**WINDOW, start_page=2, max_pages=1, per_page=20)
        )
    ]
    assert len(fetcher.calls) == 1 and fetcher.calls[0]["start"] == ["20"]
    assert pages[0][1]["page"] == 2 and len(pages[0][0].items) == 20


async def test_page_failure_preserves_originals_and_source_state_without_auto_analysis(database):
    db, config = database
    config = config.model_copy(
        update={
            "llm_model": "fixture",
            "llm_base_url": "https://fixture.example/v1",
            "llm_api_key": SecretStr("fixture-key"),
        }
    )
    source = Source(
        id="paper",
        name="Paper",
        kind="arxiv",
        url="https://rss.arxiv.org/rss/cs.AI",
        config={},
        cursor={"etag": "keep"},
        last_status="success",
        last_success_at=AT - timedelta(days=2),
    )
    async with db.sessions() as session:
        session.add(source)
        await session.commit()
    manager = TaskManager(db, config)
    manager.fetcher = ArxivFetcher(fail_second=True)
    await manager.start()
    try:
        for expected_added, expected_duplicates in [(2, 0), (0, 2)]:
            task = await manager.submit(
                "paper", backfill=BackfillRequest(**WINDOW, per_page=2, max_pages=2)
            )
            await asyncio.gather(*list(manager.workers))
            async with db.sessions() as session:
                run = await session.get(TaskRun, task.id)
                assert (run.status, run.added, run.duplicates, run.failed) == (
                    "partial",
                    expected_added,
                    expected_duplicates,
                    1,
                )
                assert run.details["plan"]["bounded"] and len(run.details["pages"]) == 2
                assert run.details["pages"][1]["status"] == "failed"
                assert run.details["pages"][1]["failed"] == 1
                assert run.details["pages"][1]["http_status"] == 503
                saved = await session.get(Source, "paper")
                assert saved.cursor == {"etag": "keep"} and saved.last_status == "success"
                assert saved.last_success_at == source.last_success_at
                assert await session.scalar(select(func.count()).select_from(Article)) == 2
                assert await session.scalar(select(func.count()).select_from(RawRecord)) == 2
                # The botany candidate is retained, with its real rule result.
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(Article)
                        .where(Article.technical_eligible.is_(False))
                    )
                    == 1
                )
            assert await AnalysisPipeline(db, config).pending_ids() == []
    finally:
        await manager.stop()


async def test_arxiv_version_and_protocol_changes_deduplicate_legacy_rss_rows(database):
    db, _ = database
    async with db.sessions() as session:
        source = Source(
            id="paper", name="Paper", kind="arxiv", url="https://rss.arxiv.org/rss/cs.AI"
        )
        session.add(source)
        await session.flush()
        original, _ = await ingest(
            session,
            source,
            RawItem(
                platform_id="http://arxiv.org/abs/2610.00001v1",
                url="http://arxiv.org/abs/2610.00001v1",
                title="LLM inference paper",
                body="Original abstract",
            ),
        )
        original.metrics = {}
        original.is_favorite = True
        await session.commit()
        incoming, outcome = await ingest(
            session,
            source,
            RawItem(
                platform_id="https://arxiv.org/abs/2610.00001v2",
                url="https://arxiv.org/abs/2610.00001v2",
                title="LLM inference paper",
                body="Updated abstract",
                defer_analysis=True,
            ),
        )
        await session.commit()
        assert incoming.id == original.id and outcome == "updated" and incoming.is_favorite
        assert await session.scalar(select(func.count()).select_from(Article)) == 1
        assert await session.scalar(select(func.count()).select_from(RawRecord)) == 2


async def test_legacy_discovery_candidacy_survives_infrastructure_refresh(database):
    db, _ = database
    async with db.sessions() as session:
        source = Source(
            id="discovery",
            name="Discovery",
            kind="github_discovery",
            url="https://api.github.com/search/repositories",
        )
        session.add(source)
        await session.flush()
        original, _ = await ingest(
            session,
            source,
            RawItem(
                platform_id="repository:1",
                title="LLM implementation",
                metrics={"kind": "repository"},
            ),
        )
        # This is the metadata format used before channels were introduced.
        original.metrics = {"kind": "repository"}
        original.is_favorite = True
        await session.flush()
        for _ in range(2):
            refreshed, _ = await ingest(
                session,
                source,
                RawItem(
                    platform_id="repository:1",
                    title="LLM implementation",
                    metrics={
                        "kind": "repository",
                        "discovery_channels": ["infrastructure"],
                        "infrastructure": {"kind": "mature"},
                    },
                ),
            )
            assert refreshed.id == original.id and refreshed.is_favorite
            assert refreshed.metrics["discovery_channels"] == ["legacy", "infrastructure"]
        new, _ = await ingest(
            session,
            source,
            RawItem(
                platform_id="repository:2",
                title="LLM new infrastructure",
                metrics={
                    "kind": "repository",
                    "discovery_channels": ["infrastructure"],
                    "infrastructure": {"kind": "mature"},
                },
            ),
        )
        assert new.metrics["discovery_channels"] == ["infrastructure"]


async def test_rss_backfill_is_explicitly_unsupported_without_a_task(client):
    response = await client.post("/api/sources/huggingface/backfill", json=WINDOW)
    assert response.status_code == 409 and "当前窗口" in response.json()["detail"]
    assert (await client.get("/api/tasks")).json() == []
    future = await client.post(
        "/api/sources/arxiv-ai/backfill/preview", json={**WINDOW, "end_date": "2026-11-06"}
    )
    assert future.status_code == 422


async def test_github_backfill_queries_created_and_pushed_without_star_or_age_cap():
    class GithubFetcher:
        settings = Settings(_env_file=None)

        def __init__(self):
            self.calls = []

        async def json(self, url, headers):
            query = parse_qs(urlsplit(url).query)
            self.calls.append(query)
            return {
                "items": [
                    {
                        "id": len(self.calls),
                        "full_name": f"fixture/llm-{len(self.calls)}",
                        "html_url": f"https://github.com/fixture/llm-{len(self.calls)}",
                        "stargazers_count": 100000,
                        "created_at": "2026-11-01T12:00:00Z",
                        "pushed_at": "2026-11-04T12:00:00Z",
                    }
                ],
                "incomplete_results": False,
            }

    fetcher = GithubFetcher()
    source = Source(kind="github_discovery", config={}, cursor={})
    pages = [
        page
        async for page in backfill_pages(
            fetcher, source, BackfillRequest(**WINDOW, topics=["llm"], per_page=2, max_pages=5)
        )
    ]
    assert len(fetcher.calls) == 2  # A short page stops each independent date query.
    assert "created:2026-10-31..2026-11-04" in fetcher.calls[0]["q"][0]
    assert "pushed:2026-10-31..2026-11-04" in fetcher.calls[1]["q"][0]
    assert all("stars:" not in query["q"][0] for query in fetcher.calls)
    assert all(
        collection.items[0].repository["observed_at"].startswith("2026-11-05")
        for collection, _ in pages
    )


def test_infrastructure_search_and_official_identity_do_not_infer_quality():
    query = infrastructure_search(0, AT, 20, ["topic:llm"], 5)
    assert "created:" not in query["q"] and "stars:>=10000" in query["q"]
    assert "50000" not in query["q"] and "pushed:>=2026-10-06" in query["q"]
    assert organization_identity("OpenAI")["evidence_url"].startswith(
        "https://platform.openai.com/"
    )
    assert organization_identity("openai-community") is None
    assert fixed_repository("Comfy-Org/ComfyUI")["catalog_name"] == "comfyanonymous/ComfyUI"


async def test_fixed_repositories_share_tracking_budget_and_reuse_etags(monkeypatch):
    class GithubFetcher:
        settings = Settings(
            github_queries_per_run=1,
            github_track_per_run=3,
            github_fixed_per_run=3,
            github_code_checks=0,
            github_history_checks=0,
            github_readme_checks=0,
            _env_file=None,
        )

        def __init__(self):
            self.calls = []

        async def json(self, url, headers):
            assert "/search/" in url
            return {"items": []}

        async def get(self, url, headers):
            self.calls.append((url, headers.copy()))
            if headers.get("If-None-Match") == "fixture-etag":
                return b"", {}, 304
            name = url.split("/repos/", 1)[1].split("/releases")[0]
            identifier = [
                "comfyanonymous/ComfyUI",
                "ggml-org/llama.cpp",
                "huggingface/diffusers",
            ].index(name) + 1
            payload = (
                []
                if "/releases" in url
                else {
                    "id": identifier,
                    "full_name": name,
                    "html_url": f"https://github.com/{name}",
                    "description": "LLM inference implementation",
                    "stargazers_count": 70000,
                    "created_at": "2018-01-01T00:00:00Z",
                    "owner": {"login": name.split("/")[0]},
                }
            )
            return json.dumps(payload).encode(), {"ETag": "fixture-etag"}, 200

    fetcher = GithubFetcher()
    source = Source(config={}, cursor={})
    first = await GitHubDiscoveryCollector(fetcher).collect(source)
    assert len(fetcher.calls) == 6 and len(first.items) == 3
    source.cursor = {**first.cursor, "fixed_tick": 0}
    second = await GitHubDiscoveryCollector(fetcher).collect(source)
    assert len(fetcher.calls) == 12 and len(second.items) == 3
    assert all(headers.get("If-None-Match") == "fixture-etag" for _, headers in fetcher.calls[6:])
    assert all(item.metrics["infrastructure"]["kind"] == "fixed" for item in second.items)
    assert not second.errors


async def test_fixed_etags_survive_other_repositories_rotating_through_the_bounded_cache():
    class EmptyFetcher:
        settings = Settings(
            github_queries_per_run=1,
            github_history_checks=0,
            github_code_checks=0,
            github_readme_checks=0,
            _env_file=None,
        )

        async def json(self, url, headers):
            return {"items": []}

    fixed_url = "https://api.github.com/repos/ggml-org/llama.cpp"
    cache = {
        f"https://api.github.com/repos/fixture/llm-{index}": {
            "etag": "other",
            "checked_at": "2026-11-05",
        }
        for index in range(80)
    }
    cache[fixed_url] = {"etag": "keep-fixed", "checked_at": "2026-10-31"}
    source = Source(config={}, cursor={"http_cache": cache})
    result = await GitHubDiscoveryCollector(EmptyFetcher()).collect(source)
    assert len(result.cursor["http_cache"]) == 64
    assert result.cursor["http_cache"][fixed_url]["etag"] == "keep-fixed"


async def test_fixed_release_failure_does_not_invent_a_successful_scan():
    class PartialFetcher:
        settings = Settings(
            github_queries_per_run=1,
            github_track_per_run=1,
            github_fixed_per_run=1,
            github_history_checks=0,
            github_code_checks=0,
            github_readme_checks=0,
            _env_file=None,
        )

        async def json(self, url, headers):
            if "/search/" in url:
                return {"items": []}
            if "/releases" in url:
                raise FetchError("fixture release failure", 503)
            return {
                "id": 1,
                "full_name": "Comfy-Org/ComfyUI",
                "html_url": "https://github.com/Comfy-Org/ComfyUI",
                "description": "LLM code implementation",
                "stargazers_count": 70000,
            }

    result = await GitHubDiscoveryCollector(PartialFetcher()).collect(Source(config={}, cursor={}))
    scan = result.cursor["scans"]["fixed:comfyanonymous/ComfyUI"]
    assert len(result.items) == 1 and result.errors
    assert scan["status"] == "partial" and scan["candidates"] == 1
    assert scan["last_success_at"] is None


async def test_common_project_stars_never_create_growth_rank(client):
    db = client._transport.app.state.db
    async with db.sessions() as session:
        source = await session.get(Source, "github-discovery")
        for index, stars in [(1, 70000), (2, 120000), (3, 90000)]:
            repo = {
                "id": index,
                "full_name": f"fixture/llm-{index}",
                "html_url": f"https://github.com/fixture/llm-{index}",
                "description": "LLM inference code implementation",
                "stargazers_count": stars,
                "language": "Python",
                "created_at": "2018-01-01T00:00:00Z",
            }
            timestamp = datetime.now(UTC)
            history = {
                "observed_at": timestamp.isoformat(),
                "days": [
                    {
                        "date": (timestamp - timedelta(days=offset)).date().isoformat(),
                        "stars": 10000,
                    }
                    for offset in range(8)
                ],
            }
            await ingest(
                session,
                source,
                RawItem(
                    platform_id=f"repository:{index}",
                    title=repo["full_name"],
                    body=repo["description"],
                    url=repo["html_url"],
                    repository={
                        "repository": repo,
                        "observed_at": timestamp.isoformat(),
                        "star_history": history,
                    },
                    metrics={
                        "kind": "repository",
                        "infrastructure": {"kind": "mature", "basis": "Cumulative stars only"},
                        "discovery_channels": ["legacy", "infrastructure"]
                        if index == 3
                        else ["infrastructure"],
                        "language": "Python",
                    },
                ),
            )
        await session.commit()
    items = (await client.get("/api/projects?pool=infrastructure")).json()["items"]
    assert [item["stars"] for item in items] == [120000, 90000, 70000]
    assert all(
        item["momentum"]["score"] == 0 and item["recommendation_score"] == 0 for item in items
    )
    rising = (await client.get("/api/projects?pool=rising")).json()["items"]
    assert [item["id"] for item in rising] == ["3"]
    assert rising[0]["momentum"]["signal"] is not None
    assert rising[0]["recommendation_score"] > 0


async def test_discovery_budget_is_explicit_persistent_and_preserves_growth(client):
    response = await client.get("/api/discovery/budget")
    original = response.json()
    values = {key: value for key, value in original.items() if key.startswith("github_")}
    assert original["max_requests"] == 35 and not original["credential_auto_increase"]
    assert (
        await client.patch("/api/discovery/budget", json={**values, "github_mature_queries": 2})
    ).status_code == 422
    values.update(
        github_queries_per_run=4,
        github_candidates_per_query=20,
        github_track_per_run=15,
        github_history_checks=15,
        github_mature_queries=1,
        github_organization_queries=1,
        github_fixed_per_run=3,
        github_search_pages=5,
    )
    saved = await client.patch("/api/discovery/budget", json=values)
    assert saved.status_code == 200 and saved.json()["max_requests"] == 54
    app = client._transport.app
    restored = await load_discovery_budget(app.state.db, Settings(_env_file=None))
    assert restored.github_fixed_per_run == 3 and restored.github_queries_per_run == 4


async def test_coverage_empty_and_bounded_backfill_do_not_fabricate_daily_coverage(database):
    db, _ = database
    async with db.sessions() as session:
        source = Source(
            id="empty",
            name="Empty",
            kind="rss",
            url="https://huggingface.co/feed.xml",
            enabled=True,
            config={},
            cursor={},
        )
        session.add(source)
        await session.flush()
        session.add(
            TaskRun(
                source_id="empty",
                kind="backfill",
                status="partial",
                created_at=AT,
                details={"plan": WINDOW},
                added=1,
            )
        )
        await session.commit()
        report = await coverage_audit(session, AT)
        row = report["sources"][0]
        assert (
            row["last_success_at"] is None and len(row["days_without_successful_collection"]) == 7
        )
        assert row["groups"] == [] and not row["backfill"]["supported"]
        assert row["totals_7d"]["added"] == 1


async def test_coverage_lists_unscanned_groups_and_preserves_old_scope_evidence(database):
    db, config = database
    config = config.model_copy(update={"github_fixed_per_run": 1})
    async with db.sessions() as session:
        session.add(
            Source(
                id="discovery",
                name="Discovery",
                kind="github_discovery",
                url="https://api.github.com/search/repositories",
                config={"discovery_topics": ["llm"]},
                cursor={
                    "scans": {
                        "old-scope": {
                            "label": "Old scope",
                            "candidates": 2,
                            "last_scan_at": AT.isoformat(),
                        },
                    }
                },
            )
        )
        await session.commit()
        report = await coverage_audit(session, AT, config)
        groups = {group["id"]: group for group in report["sources"][0]["groups"]}
        assert groups["llm"]["candidates"] is None
        assert groups["llm"]["gaps"] == ["尚无扫描证据"]
        assert groups["fixed:ggml-org/llama.cpp"]["last_success_at"] is None
        assert groups["old-scope"]["candidates"] == 2
        assert groups["old-scope"]["filtered"] is None


async def test_arxiv_requests_and_retries_are_serialized_at_least_three_seconds_apart(monkeypatch):
    clock = [0.0]
    starts = []
    fetcher = Fetcher(Settings(_env_file=None))

    async def sleep(delay):
        clock[0] += delay

    async def perform(url, headers):
        starts.append(clock[0])
        if len(starts) == 1:
            raise FetchError("fixture temporary failure", 503)
        return b"ok", {}, 200

    monkeypatch.setattr(network.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(network.asyncio, "sleep", sleep)
    monkeypatch.setattr(fetcher, "_perform_request", perform)
    await fetcher.get("https://export.arxiv.org/api/query?start=0")
    await fetcher.get("https://export.arxiv.org/api/query?start=20")
    assert starts == [0.0, 3.0, 6.0]


async def test_busy_source_does_not_abort_other_scheduler_sources(database, monkeypatch):
    db, config = database
    async with db.sessions() as session:
        session.add_all(
            [
                Source(id=key, name=key, kind="rss", url="https://huggingface.co/feed.xml")
                for key in ["busy", "other"]
            ]
        )
        await session.commit()
    manager = TaskManager(db, config)
    calls = []

    async def submit(key):
        calls.append(key)
        if key == "busy":
            raise ValueError("A bounded backfill is already running")

    monkeypatch.setattr(manager, "submit", submit)
    await manager.tick()
    assert calls == ["busy", "other"]
