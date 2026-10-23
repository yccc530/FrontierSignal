import hashlib
import json

import httpx
import pytest
from frontiersignal.analysis import AnalysisPipeline, seed_categories
from frontiersignal.llm import AnalysisResult, Completion, LLMProvider, ProviderError
from frontiersignal.models import AnalysisAttempt, Article, RawRecord, Source
from frontiersignal.normalizer import RawItem
from frontiersignal.similarity import compute_simhash, hamming_distance, link_related
from frontiersignal.storage import ingest
from simhash import Simhash
from sqlalchemy import func, select

RESULT = {
    "is_ai_related": True,
    "title_zh": "新人工智能模型发布",
    "summary_zh": "测试模型发布，需核实实际能力。",
    "category": "models",
    "tags": ["模型"],
    "score": 65,
    "evidence": "仅基于提供的来源文字，未独立验证。",
}


def test_simhash_large_feature_counts_preserve_full_weights():
    expected = int.from_bytes(hashlib.md5(b"aaaa").digest()[-8:], "big", signed=True)
    assert compute_simhash("a" * 100_000) == expected
    text = "A new open source model release with detailed technical evidence"
    original = Simhash(text).value
    signed = original - (1 << 64) if original >= (1 << 63) else original
    assert compute_simhash(text) == signed


def configured(settings):
    return settings.model_copy(
        update={
            "llm_base_url": "https://llm.example/v1",
            "llm_model": "test-model",
            "llm_api_key": type(settings.llm_api_key)("test-secret"),
            "llm_max_retries": 0,
        }
    )


async def make_article(db):
    async with db.sessions() as session:
        await seed_categories(session)
        source = Source(id="test", name="Test", kind="rss", url="https://example.com")
        session.add(source)
        await session.flush()
        article, _ = await ingest(
            session,
            source,
            RawItem(platform_id="1", title="New LLM inference benchmark", body="Original source"),
        )
        await session.commit()
        return article.id


async def test_provider_minimal_payload_and_json_validation(database):
    _, settings = database

    def handle(request):
        payload = json.loads(request.content)
        assert set(payload) == {"model", "messages"}
        assert request.url.path == "/v1/chat/completions"
        assert "test-secret" not in str(payload)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(RESULT)}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 30},
            },
        )

    provider = LLMProvider(configured(settings), httpx.MockTransport(handle))
    completion = await provider.analyze("title", "body", {"models": "Models"})
    assert completion.result.score == 65 and completion.input_tokens == 100


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        json.dumps({**RESULT, "score": 101}),
        json.dumps({**RESULT, "summary_zh": "English only"}),
        json.dumps({**RESULT, "title_zh": "English only"}),
        json.dumps({**RESULT, "category": "unknown"}),
    ],
)
async def test_invalid_result_is_failure(database, content):
    _, settings = database
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
    )
    with pytest.raises(ProviderError):
        await LLMProvider(configured(settings), transport).analyze("x", "y", {"models": "Models"})


async def test_failure_retry_preserves_raw_and_success_not_repeated(database):
    db, settings = database
    article_id = await make_article(db)

    class Provider:
        calls = 0
        fail = True

        async def analyze(self, *args):
            self.calls += 1
            if self.fail:
                raise ProviderError("LLM HTTP 503")
            return Completion(AnalysisResult(**RESULT), 100, 30)

    provider = Provider()
    pipeline = AnalysisPipeline(db, configured(settings), provider)
    assert await pipeline.process(article_id) == "failed"
    async with db.sessions() as session:
        assert await session.scalar(select(func.count()).select_from(RawRecord)) == 1
        assert (await session.get(Article, article_id)).body == "Original source"
    provider.fail = False
    assert await pipeline.process(article_id) == "analyzed"
    assert await pipeline.process(article_id) == "skipped"
    assert provider.calls == 2
    async with db.sessions() as session:
        attempts = (
            await session.scalars(select(AnalysisAttempt).order_by(AnalysisAttempt.created_at))
        ).all()
        assert [a.status for a in attempts] == ["failed", "success"]
        assert (await session.get(Article, article_id)).summary_zh == RESULT["summary_zh"]
        assert (await session.get(Article, article_id)).title_zh == RESULT["title_zh"]
        assert (await session.get(Article, article_id)).title == "New LLM inference benchmark"


async def test_changed_content_during_call_does_not_publish_stale_analysis(database):
    db, settings = database
    article_id = await make_article(db)

    class Provider:
        async def analyze(self, *args):
            async with db.sessions() as session:
                source = await session.get(Source, "test")
                await ingest(
                    session,
                    source,
                    RawItem(platform_id="1", title="Changed title", body="Changed body"),
                )
                await session.commit()
            return Completion(AnalysisResult(**RESULT), None, None)

    assert (
        await AnalysisPipeline(db, configured(settings), Provider()).process(article_id) == "stale"
    )
    async with db.sessions() as session:
        article = await session.get(Article, article_id)
        assert article.summary_zh is None and article.status == "pending"


async def test_linking_preserves_both_reports(database):
    from frontiersignal.models import ArticleLink

    db, _ = database
    async with db.sessions() as session:
        for name in ["a", "b"]:
            source = Source(id=name, name=name, kind="rss", url="https://example.com")
            session.add(source)
            await session.flush()
            article, _ = await ingest(
                session, source, RawItem(title="Test AI release", url="https://example.com/story")
            )
            await link_related(session, article)
        await session.commit()
        assert await session.scalar(select(func.count()).select_from(Article)) == 2
        assert await session.scalar(select(func.count()).select_from(ArticleLink)) == 1
    assert hamming_distance(-1, 0) == 64


async def test_unconfigured_analysis_reports_error_and_settings_hide_keys(client):
    response = await client.post("/api/analyze")
    assert response.status_code == 409
    data = (await client.get("/api/settings")).json()
    assert "llm_api_key" not in data and data["llm_key_configured"] is False
    assert (await client.get("/api/categories")).json()


async def test_transient_failure_retries_with_audited_attempts(database):
    db, settings = database
    article_id = await make_article(db)
    config = configured(settings).model_copy(update={"llm_max_retries": 1})
    calls = []

    def handle(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(RESULT)}}]})

    pipeline = AnalysisPipeline(db, config, LLMProvider(config, httpx.MockTransport(handle)))
    assert await pipeline.process(article_id) == "analyzed"
    assert len(calls) == 2
    async with db.sessions() as session:
        assert await session.scalar(select(func.count()).select_from(AnalysisAttempt)) == 2


async def test_empty_analysis_queue_is_not_false_success(database):
    from frontiersignal.tasks import TaskManager

    db, settings = database
    manager = TaskManager(db, configured(settings))
    await manager.start()
    with pytest.raises(ValueError, match="没有到期"):
        await manager.submit_analysis()
    await manager.stop()
