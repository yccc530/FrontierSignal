from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from frontiersignal.analysis import AnalysisPipeline
from frontiersignal.collectors.github_discovery import GitHubDiscoveryCollector
from frontiersignal.collectors.hackernews import HackerNewsCollector
from frontiersignal.config import Settings
from frontiersignal.models import (
    Article,
    ArticleLink,
    RawRecord,
    Repository,
    Source,
    StarSnapshot,
    now,
)
from frontiersignal.network import FetchError
from frontiersignal.normalizer import RawItem
from frontiersignal.projects import star_growth
from frontiersignal.recommendations import article_rank, recency
from frontiersignal.similarity import link_related
from frontiersignal.storage import ingest
from frontiersignal.technical import technical_signal
from sqlalchemy import func, select

AT = datetime(2026, 10, 22, 8, tzinfo=UTC)


def snapshot(hours, stars):
    return SimpleNamespace(observed_at=AT - timedelta(hours=hours), stars=stars)


@pytest.mark.parametrize(
    "history, expected",
    [
        ([snapshot(0, 10)], None),
        ([snapshot(0, 20), snapshot(23, 10)], None),
        ([snapshot(0, 20), snapshot(24, 10)], 10),
        ([snapshot(0, 20), snapshot(25, 20)], 0),
        ([snapshot(0, 15), snapshot(24, 20)], -5),
        ([snapshot(0, 20), snapshot(31, 10)], None),
        ([snapshot(7, 20), snapshot(31, 10)], None),
        ([snapshot(-1, 9999), snapshot(0, 20), snapshot(24, 10)], 10),
    ],
)
def test_observed_star_growth_windows_unknown_zero_negative_and_stale(history, expected):
    result = star_growth(history, AT, 1)
    assert result["value"] == expected
    if expected is not None:
        assert 24 <= result["window_hours"] <= 30


def test_seven_day_growth_requires_real_week_baseline():
    assert star_growth([snapshot(0, 500), snapshot(24, 400)], AT, 7)["value"] is None
    result = star_growth([snapshot(0, 500), snapshot(168, 300)], AT, 7)
    assert result["value"] == 200 and result["window_hours"] == 168
    assert recency(AT + timedelta(days=1), AT, 24) == 0
    assert recency(None, AT, 24) == 0


def test_technical_rules_separate_research_from_marketing():
    useful = technical_signal(
        "LLM inference benchmark",
        "Open source implementation and reproducible training experiments",
        "hackernews",
    )
    noisy = technical_signal(
        "AI startup funding valuation and celebrity news", "Marketing giveaway", "hackernews"
    )
    assert useful.eligible and {"llm", "inference", "evaluation"} <= set(useful.topics)
    assert not noisy.eligible
    catalog = technical_signal(
        "org/awesome-llm", "A curated list of language models", "github_discovery"
    )
    assert not catalog.eligible


def repo_payload(stars=100):
    return {
        "id": 42,
        "full_name": "fixture/llm-inference",
        "html_url": "https://github.com/fixture/llm-inference",
        "description": "LLM inference training benchmark implementation",
        "stargazers_count": stars,
        "forks_count": 3,
        "size": 100,
        "language": "Python",
        "license": {"spdx_id": "MIT"},
        "topics": ["llm", "inference"],
        "created_at": "2026-01-01T00:00:00Z",
        "pushed_at": AT.isoformat(),
        "updated_at": AT.isoformat(),
        "owner": {"login": "fixture"},
        "archived": False,
        "fork": False,
        "private": False,
    }


def repo_item(stars=100, observed=AT):
    repo = repo_payload(stars)
    observation = {"repository": repo, "observed_at": observed.isoformat()}
    return RawItem(
        platform_id="repository:42",
        title=repo["full_name"],
        body=repo["description"],
        url=repo["html_url"],
        raw=observation,
        metrics={
            "kind": "repository",
            "stars": stars,
            "topics": repo["topics"],
            "language": "Python",
        },
        repository=observation,
    )


async def test_repository_snapshots_do_not_repeat_articles_or_llm_analysis(database):
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
        article, result = await ingest(session, source, repo_item())
        assert result == "added"
        article.status, article.summary_zh, article.analysis_hash = (
            "analyzed",
            "已有真实分析的测试夹具",
            "done",
        )
        await session.commit()
        repeated, result = await ingest(session, source, repo_item(110, AT + timedelta(minutes=10)))
        await session.commit()
        assert result == "duplicates" and repeated.id == article.id
        assert repeated.status == "analyzed" and repeated.analysis_hash == "done"
        assert await session.scalar(select(func.count()).select_from(StarSnapshot)) == 1
        final_time = AT + timedelta(hours=24, minutes=10)
        await ingest(session, source, repo_item(120, final_time))
        await session.commit()
        assert await session.scalar(select(func.count()).select_from(Article)) == 1
        assert await session.scalar(select(func.count()).select_from(RawRecord)) == 3
        history = list((await session.scalars(select(StarSnapshot))).all())
        assert star_growth(history, final_time, 1)["value"] == 10
        assert (await session.get(Repository, "42")).stars == 120


async def test_hn_duplicate_event_preserves_distinct_discussions_and_links(database):
    db, _ = database
    async with db.sessions() as session:
        source = Source(
            id="hn", name="HN", kind="hackernews", url="https://hacker-news.firebaseio.com"
        )
        session.add(source)
        await session.flush()
        for number in [1, 2]:
            item = RawItem(
                platform_id=str(number),
                title="LLM inference benchmark with reproducible code",
                body="Benchmark implementation " * 20,
                url="https://example.com/research",
                identity_url=f"https://news.ycombinator.com/item?id={number}",
            )
            article, _ = await ingest(session, source, item)
            await link_related(session, article)
        await session.commit()
        assert await session.scalar(select(func.count()).select_from(Article)) == 2
        assert await session.scalar(select(func.count()).select_from(ArticleLink)) == 1


async def test_github_search_quality_and_release_collection_uses_official_api():
    class Fetcher:
        settings = Settings(
            github_queries_per_run=1, github_track_per_run=1, github_code_checks=1, _env_file=None
        )
        calls = []

        async def json(self, url, headers):
            assert urlsplit(url).hostname == "api.github.com"
            self.calls.append(url)
            if "/search/" in url:
                query = parse_qs(urlsplit(url).query)["q"][0]
                assert "fork:false" in query and "pushed:" in query
                return {"items": [repo_payload()], "incomplete_results": False}
            if "/contents" in url:
                return [{"type": "file", "name": "train.py"}]
            if "/readme" in url:
                import base64

                return {
                    "sha": "a" * 40,
                    "encoding": "base64",
                    "content": base64.b64encode(b"Open neural training implementation").decode(),
                }
            if "/stargazers/history" in url:
                return []
            if "/releases" in url:
                return [
                    {
                        "id": 7,
                        "tag_name": "v1",
                        "body": "LLM inference benchmark",
                        "html_url": "https://github.com/fixture/llm-inference/releases/tag/v1",
                        "published_at": AT.isoformat(),
                    }
                ]
            return repo_payload()

    result = await GitHubDiscoveryCollector(Fetcher()).collect(Source(cursor={}))
    assert len(result.items) == 2 and not result.errors
    assert result.items[0].repository["has_code"] is True
    assert result.items[0].repository["latest_release"]["tag_name"] == "v1"
    assert result.items[1].platform_id == "release:7"
    assert result.cursor["discovery_tick"] == 1 and result.cursor["strategy"] == 2


async def test_github_search_failure_does_not_discard_other_queries():
    class Fetcher:
        settings = Settings(github_queries_per_run=2, github_code_checks=0, _env_file=None)

        async def json(self, url, headers):
            if "/search/" in url:
                if "ai+agent" in url.lower() or "AI+agent" in url:
                    raise FetchError("private response", 403)
                return {"items": [repo_payload()]}
            if "/releases" in url:
                return []
            if "/stargazers/history" in url:
                return []
            return repo_payload()

    result = await GitHubDiscoveryCollector(Fetcher()).collect(Source(cursor={}))
    assert result.items and result.errors and result.advance_on_partial
    assert "private response" not in str(result.errors)


async def test_hn_comments_and_metrics_are_observed_without_body_rewrites():
    class Fetcher:
        settings = Settings(hn_candidates=10, hn_comment_limit=2, _env_file=None)

        async def json(self, url):
            if "stories" in url:
                return [1]
            if "item/2" in url:
                return {
                    "id": 2,
                    "type": "comment",
                    "by": "tester",
                    "text": "<p>Measured benchmark results</p>",
                    "time": 100,
                }
            return {
                "id": 1,
                "title": "LLM inference training benchmark",
                "score": 99,
                "descendants": 12,
                "kids": [2],
                "time": 100,
                "url": "https://example.com/paper",
            }

    result = await HackerNewsCollector(Fetcher()).collect(None)
    assert len(result.items) == 1
    article = result.items[0]
    assert article.metrics["points"] == 99 and article.metrics["comments_count"] == 12
    assert article.metrics["comments_sample"][0]["text"] == "Measured benchmark results"
    assert article.body == "" and article.identity_url.endswith("id=1")


async def test_recommendation_api_preserves_unknown_growth_and_deduplicates(client, database):
    db, _ = database
    at = now()
    async with db.sessions() as session:
        source = await session.get(Source, "github-discovery")
        await ingest(session, source, repo_item(100, at))
        hn = await session.get(Source, "hackernews")
        for identifier in [1, 2]:
            article, _ = await ingest(
                session,
                hn,
                RawItem(
                    platform_id=str(identifier),
                    title="LLM inference training benchmark",
                    body="Open source implementation and experiments",
                    published_at=at,
                    url="https://example.com/event",
                    identity_url=f"https://news.ycombinator.com/item?id={identifier}",
                    metrics={"points": 100, "comments_count": 30},
                ),
            )
            await link_related(session, article)
        await session.commit()
    response = await client.get("/recommendations")
    assert response.status_code == 404  # Endpoints only exist under the local API boundary.
    dashboard = (await client.get("/api/recommendations")).json()
    assert dashboard["projects"] == []
    assert dashboard["emerging_projects"] == []
    assert (await client.get("/api/projects")).json()["items"] == []
    archive = (await client.get("/api/projects?pool=all")).json()
    assert archive["items"][0]["growth_24h"]["value"] is None
    assert archive["items"][0]["momentum"]["is_new"] is False
    assert (
        len(next(section for section in dashboard["sections"] if section["id"] == "hot")["items"])
        == 1
    )
    all_ids = [
        item["article"]["id"] for section in dashboard["sections"] for item in section["items"]
    ]
    assert len(all_ids) == len(set(all_ids))
    history = (await client.get("/api/projects/42/history")).json()
    assert len(history) == 1 and history[0]["stars"] == 100
    assert (await client.get("/api/projects?topic=unknown")).status_code == 422
    for kind in ["x", "reddit"]:
        assert (
            await client.post("/api/sources", json={"name": "Removed", "kind": kind})
        ).status_code == 422


async def test_preferences_are_validated_and_persist_without_secrets(client, monkeypatch, tmp_path):
    monkeypatch.setattr("frontiersignal.discovery_api.PROJECT_ROOT", tmp_path)
    assert (await client.patch("/api/preferences", json={"topics": []})).status_code == 422
    assert (await client.patch("/api/preferences", json={"topics": ["bad"]})).status_code == 422
    response = await client.patch("/api/preferences", json={"topics": ["inference", "agents"]})
    assert response.status_code == 200
    assert (await client.get("/api/settings")).json()["interest_topics"] == ["inference", "agents"]
    assert "FS_INTEREST_TOPICS" in (tmp_path / ".env").read_text()


async def test_filtered_project_leaves_recommendations_but_keeps_original_and_history(
    client, database
):
    db, _ = database
    async with db.sessions() as session:
        source = await session.get(Source, "github-discovery")
        article, _ = await ingest(session, source, repo_item(100, now()))
        article.status = "filtered"
        await session.commit()
        article_id = article.id
    assert (await client.get("/api/projects")).json()["total"] == 0
    assert (await client.get("/api/recommendations")).json()["projects"] == []
    original = (await client.get(f"/api/articles/{article_id}")).json()
    assert original["title"] == "fixture/llm-inference"
    assert original["raw_versions"] == 1
    assert len((await client.get("/api/projects/42/history")).json()) == 1


def test_platform_metrics_do_not_enter_cross_source_value_ranking():
    source = SimpleNamespace(kind="hackernews", trust="community")
    article = SimpleNamespace(
        technical_score=80,
        technical_reasons=[],
        published_at=AT,
        collected_at=AT,
        technical_topics=["llm"],
        score=None,
        is_ai_related=None,
        source=source,
        is_read=False,
        metrics={"points": 1, "comments_count": 1},
    )
    first = article_rank(article, AT, ["llm"], include_heat=False)[0]
    article.metrics = {"points": 100000, "comments_count": 100000}
    assert article_rank(article, AT, ["llm"], include_heat=False)[0] == first
    assert article_rank(article, AT, ["llm"], include_heat=True)[0] > first


def test_hn_hot_discussion_can_outrank_low_engagement_new_post():
    source = SimpleNamespace(kind="hackernews", trust="community")
    common = dict(
        technical_score=70,
        technical_reasons=[],
        collected_at=AT,
        technical_topics=["llm"],
        score=None,
        is_ai_related=None,
        source=source,
        is_read=False,
    )
    hot = SimpleNamespace(
        **common,
        published_at=AT - timedelta(hours=48),
        metrics={"points": 2300, "comments_count": 200},
    )
    new = SimpleNamespace(
        **common,
        published_at=AT - timedelta(minutes=10),
        metrics={"points": 2, "comments_count": 0},
    )
    assert article_rank(hot, AT, ["llm"])[0] > article_rank(new, AT, ["llm"])[0]


async def test_new_repository_analysis_uses_discovery_time_not_creation_year(database):
    db, settings = database
    async with db.sessions() as session:
        source = Source(
            id="discovery",
            name="Discovery",
            kind="github_discovery",
            url="https://api.github.com/search/repositories",
        )
        session.add(source)
        await session.flush()
        item = repo_item()
        item.published_at = now() - timedelta(days=365)
        project, _ = await ingest(session, source, item)
        other, _ = await ingest(
            session,
            source,
            RawItem(
                platform_id="release:1",
                title="LLM inference benchmark release",
                body="Training implementation",
                published_at=now() - timedelta(hours=1),
            ),
        )
        await session.commit()
    pending = await AnalysisPipeline(db, settings).pending_ids()
    assert pending.index(project.id) < pending.index(other.id)
