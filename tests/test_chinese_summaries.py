from datetime import timedelta

import pytest
from frontiersignal.analysis import AnalysisPipeline, seed_categories
from frontiersignal.chinese_summaries import summary_coverage
from frontiersignal.llm import AnalysisResult, Completion, ProviderError
from frontiersignal.models import (
    AnalysisAttempt,
    Article,
    RawRecord,
    RecommendationView,
    Source,
    TaskRun,
    WorkbenchState,
    now,
)
from frontiersignal.normalizer import RawItem
from frontiersignal.storage import ingest
from sqlalchemy import func, select
from test_analysis import RESULT, configured


async def make_record(db, key, **values):
    async with db.sessions() as session:
        await seed_categories(session)
        source = Source(id=key, name=key, kind="rss", url="https://example.com/" + key)
        session.add(source)
        await session.flush()
        article, _ = await ingest(
            session,
            source,
            RawItem(
                platform_id="record", title="New LLM inference benchmark", body="Original evidence"
            ),
        )
        for name, value in values.items():
            setattr(article, name, value)
        await session.commit()
        return article.id


async def enable_all(db):
    async with db.sessions() as session:
        session.add(WorkbenchState(id="chinese-summaries", value={"all_content": True}))
        await session.commit()


class Provider:
    def __init__(self, failure=False):
        self.calls = 0
        self.failure = failure

    async def analyze(self, *args):
        self.calls += 1
        if self.failure:
            raise ProviderError("模型返回内容未通过格式或中文校验")
        return Completion(AnalysisResult(**RESULT), 20, 30)


async def test_all_scope_includes_deferred_and_filtered_without_promoting_them(database):
    db, settings = database
    filtered = await make_record(db, "filtered", status="filtered", is_ai_related=False)
    deferred = await make_record(db, "deferred")
    async with db.sessions() as session:
        article = await session.get(Article, deferred)
        article.metrics = {"analysis_deferred_hash": article.content_hash}
        await session.commit()
    pipeline = AnalysisPipeline(db, configured(settings), Provider())
    assert await pipeline.pending_ids() == []
    await enable_all(db)
    assert set(await pipeline.pending_ids()) == {filtered, deferred}
    assert await pipeline.process(filtered) == "filtered"
    async with db.sessions() as session:
        article = await session.get(Article, filtered)
        assert article.summary_zh == RESULT["summary_zh"]
        assert article.title_zh == RESULT["title_zh"]
        assert article.is_ai_related is False
        assert article.body == "Original evidence"
        assert article.metrics.get("analysis_deferred_hash") is None
        assert await session.scalar(select(func.count()).select_from(RawRecord)) == 2
    assert await pipeline.process(deferred) == "analyzed"
    assert await pipeline.pending_ids() == []


async def test_all_scope_keeps_rule_filters_while_generating_chinese(database):
    db, settings = database
    article_id = await make_record(db, "unrelated", technical_eligible=False)
    await enable_all(db)
    provider = Provider()
    pipeline = AnalysisPipeline(db, configured(settings), provider)
    assert await pipeline.process(article_id) == "filtered"
    assert provider.calls == 1
    async with db.sessions() as session:
        article = await session.get(Article, article_id)
        assert article.technical_eligible is False
        assert article.summary_zh == RESULT["summary_zh"]
    assert await pipeline.process(article_id) == "skipped"
    assert provider.calls == 1


async def test_exact_reuse_keeps_source_records_and_does_not_invent_a_call(database):
    db, settings = database
    first = await make_record(db, "first")
    second = await make_record(db, "second")
    provider = Provider()
    pipeline = AnalysisPipeline(db, configured(settings), provider)
    assert await pipeline.process(first) == "analyzed"
    assert await pipeline.process(second) == "analyzed"
    assert provider.calls == 1
    async with db.sessions() as session:
        attempts = (await session.scalars(select(AnalysisAttempt))).all()
        article = await session.get(Article, second)
        assert len(attempts) == 1 and attempts[0].article_id == first
        assert article.metrics["chinese_summary_reuse"]["attempt_id"] == attempts[0].id
        assert article.analysis_attempts == 0
        assert await session.scalar(select(func.count()).select_from(Article)) == 2
        assert await session.scalar(select(func.count()).select_from(RawRecord)) == 2


async def test_new_original_content_does_not_keep_old_reuse_provenance(database):
    db, settings = database
    first = await make_record(db, "first")
    second = await make_record(db, "second")
    provider = Provider()
    pipeline = AnalysisPipeline(db, configured(settings), provider)
    await pipeline.process(first)
    await pipeline.process(second)
    async with db.sessions() as session:
        article = await session.get(Article, second)
        assert article.metrics["chinese_summary_reuse"]
        source = await session.get(Source, "second")
        await ingest(
            session,
            source,
            RawItem(
                platform_id="record",
                title="New LLM inference benchmark",
                body="Changed original evidence",
            ),
        )
        await session.commit()
    assert await pipeline.process(second) == "analyzed"
    assert provider.calls == 2
    async with db.sessions() as session:
        article = await session.get(Article, second)
        assert "chinese_summary_reuse" not in article.metrics
        assert article.body == "Changed original evidence"
        assert await session.scalar(select(func.count()).select_from(RawRecord)) == 3


@pytest.mark.parametrize("change", ["model", "input", "categories", "invalid_cache"])
async def test_reuse_requires_the_same_valid_request(database, change):
    db, settings = database
    first = await make_record(db, "first")
    second = await make_record(db, "second")
    config, provider = configured(settings), Provider()
    await AnalysisPipeline(db, config, provider).process(first)
    if change == "model":
        config = config.model_copy(update={"llm_model": "other-model"})
    else:
        async with db.sessions() as session:
            if change == "input":
                article = await session.get(Article, second)
                article.content_hash = "changed-input-hash"
            elif change == "categories":
                from frontiersignal.models import Category

                session.add(Category(id="extra", label="其他"))
            else:
                attempt = await session.scalar(select(AnalysisAttempt))
                attempt.result = {**RESULT, "summary_zh": "English only"}
            await session.commit()
    assert await AnalysisPipeline(db, config, provider).process(second) == "analyzed"
    assert provider.calls == 2


async def test_queue_prioritizes_shown_content_and_reserves_historical_capacity(database):
    db, settings = database
    await enable_all(db)
    oldest = await make_record(db, "oldest", collected_at=now() - timedelta(days=100))
    recent = [await make_record(db, str(i)) for i in range(6)]
    async with db.sessions() as session:
        session.add(
            RecommendationView(
                article_id=oldest,
                revision_hash="version",
                first_shown_at=now(),
                last_shown_at=now(),
            )
        )
        blocked = await session.get(Article, recent[0])
        blocked.analysis_attempts = 3
        retrying = await session.get(Article, recent[1])
        retrying.retry_at = now() + timedelta(days=1)
        await session.commit()
    queue = await AnalysisPipeline(db, configured(settings)).pending_ids()
    assert len(queue) == 5 and queue[0] == oldest
    assert recent[0] not in queue and recent[1] not in queue
    async with db.sessions() as session:
        await session.delete(await session.get(RecommendationView, (oldest, "version")))
        await session.commit()
    queue = await AnalysisPipeline(db, configured(settings)).pending_ids()
    assert oldest in queue


async def test_filtered_summary_failure_is_bounded_and_does_not_reenter_recommendations(database):
    db, settings = database
    article_id = await make_record(db, "filtered", status="filtered", is_ai_related=False)
    await enable_all(db)
    provider = Provider(failure=True)
    pipeline = AnalysisPipeline(db, configured(settings), provider)
    for _ in range(3):
        assert await pipeline.process(article_id) == "failed"
    assert await pipeline.pending_ids() == []
    async with db.sessions() as session:
        article = await session.get(Article, article_id)
        assert article.status == "filtered" and article.is_ai_related is False
        assert article.summary_zh is None and article.retry_at is not None
        report = await summary_coverage(session, settings)
        assert report["failed"] == 1 and report["ready"] == 0


async def test_interface_probe_is_not_reported_as_a_successful_chinese_summary(database):
    db, settings = database
    async with db.sessions() as session:
        session.add(TaskRun(kind="probe", status="success", finished_at=now()))
        await session.commit()
        report = await summary_coverage(session, settings)
        assert report["total"] == 0 and report["last_success_at"] is None


async def test_policy_and_retry_endpoints_are_explicit_bounded_and_preserve_ready_content(
    client, database
):
    db, _ = database
    failed = await make_record(db, "failed", status="failed", analysis_attempts=3)
    ready = await make_record(
        db,
        "ready",
        status="analyzed",
        analysis_attempts=3,
        title_zh=RESULT["title_zh"],
        summary_zh=RESULT["summary_zh"],
    )
    before = (await client.get("/api/chinese-summaries")).json()
    assert before["policy"] == {"all_content": False}
    assert before["total"] == 2 and before["ready"] == 1 and before["failed"] == 1
    assert (
        await client.patch("/api/chinese-summaries", json={"all_content": "true"})
    ).status_code == 422
    enabled = (await client.patch("/api/chinese-summaries", json={"all_content": True})).json()
    assert enabled["policy"] == {"all_content": True}
    assert (
        await client.post("/api/chinese-summaries/retry", json={"limit": 101})
    ).status_code == 422
    result = (await client.post("/api/chinese-summaries/retry", json={"limit": 1})).json()
    assert result["queued"] == 1
    async with db.sessions() as session:
        assert (await session.get(Article, failed)).analysis_attempts == 0
        assert (await session.get(Article, ready)).analysis_attempts == 3
        assert (await session.get(TaskRun, result["task_id"])).kind == "summary_retry"
        assert await session.scalar(select(func.count()).select_from(AnalysisAttempt)) == 0
        assert (await session.get(WorkbenchState, "chinese-summaries")).value == {
            "all_content": True
        }
