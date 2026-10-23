from copy import deepcopy
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

from frontiersignal.collectors.huggingface import HuggingFaceCollector, model_groups, model_query
from frontiersignal.config import Settings
from frontiersignal.model_info import annotate_official_model, model_metadata
from frontiersignal.models import Article, ArticleLink, RawRecord, Source, now
from frontiersignal.network import FetchError
from frontiersignal.normalizer import RawItem
from frontiersignal.recommendations import activity_time, article_rank
from frontiersignal.similarity import link_related
from frontiersignal.storage import ingest
from sqlalchemy import func, select


def model_payload(identifier="Qwen/Fixture-Coder", revision="a" * 40):
    return {
        "id": identifier,
        "author": identifier.split("/")[0],
        "sha": revision,
        "createdAt": "2025-01-01T00:00:00Z",
        "lastModified": now().isoformat(),
        "pipeline_tag": "text-generation",
        "private": False,
        "gated": False,
        "downloads": 20,
        "likes": 2,
        "tags": ["text-generation", "code-generation", "transformers"],
        "cardData": {"license": "apache-2.0"},
        "siblings": [{"rfilename": "README.md"}, {"rfilename": "model.safetensors"}],
    }


class ModelFetcher:
    settings = Settings(hf_queries_per_run=1, hf_card_checks=1, _env_file=None)

    def __init__(self, payload=None, failure=None):
        self.payload = payload or model_payload()
        self.failure = failure
        self.calls = []

    async def json(self, url):
        self.calls.append(url)
        assert url.startswith("https://huggingface.co/api/models?")
        return [deepcopy(self.payload)]

    async def get(self, url):
        self.calls.append(url)
        assert url.endswith("/README.md") and "/resolve/" in url
        if self.failure:
            raise self.failure
        return (
            b"# Fixture code generation model\nTraining implementation with a reproducible benchmark.\n[Code](https://github.com/fixture/coder) [Paper](https://arxiv.org/abs/2601.00001)",
            {},
            200,
        )


def test_model_query_rotation_covers_topics_publishers_and_freshness_with_bounded_limits():
    source = Source(
        kind="hf_models", config={"discovery_topics": ["llm", "multimodal", "coding_models", "ocr"]}
    )
    groups = model_groups(source)
    queries = [model_query(source, tick, 5) for tick in range(216)]
    assert {group["id"] for group, _ in queries} == {group["id"] for group in groups}
    assert sum(group["lane"] == "global" for group, _ in queries) == 18
    assert sum(group["lane"] == "topic" for group, _ in queries) == 90
    assert {params["sort"] for group, params in queries if group["lane"] == "topic"} == {
        "createdAt",
        "lastModified",
        "trendingScore",
    }
    assert all(params["limit"] == 5 and params["full"] == "true" for _, params in queries)
    narrow = Source(kind="hf_models", config={"discovery_topics": ["ocr"]})
    assert all(set(group["topics"]) == {"ocr"} for group in model_groups(narrow))


def test_metadata_never_invents_release_version_license_or_publisher_identity():
    payload = model_payload("community/GPT-999")
    payload["author"] = "openai"
    payload["cardData"] = {}
    payload["siblings"] = []
    metadata = model_metadata(payload)
    assert metadata["publisher_verified"] is False and metadata["publisher_id"] is None
    assert metadata["version"] is None and metadata["release_at"] is None
    assert metadata["access"] == "unknown" and metadata["license"] is None
    assert metadata["hub_created_at"] == payload["createdAt"]
    gated = model_payload()
    gated["gated"] = "auto"
    assert model_metadata(gated)["access"] == "gated_weights"


async def test_card_revision_cache_and_failure_keep_body_analysis_and_identity(database):
    db, _ = database
    source = Source(
        id="models",
        name="Model fixture",
        kind="hf_models",
        url="https://huggingface.co/api/models",
        config={},
        cursor={},
    )
    fetcher = ModelFetcher()
    first = await HuggingFaceCollector(fetcher).collect(source)
    assert len(first.items) == 1 and not first.errors
    assert first.items[0].published_at is None
    async with db.sessions() as session:
        session.add(source)
        await session.flush()
        article, outcome = await ingest(session, source, first.items[0])
        assert outcome == "added" and article.technical_eligible
        article.status, article.summary_zh, article.analysis_hash = (
            "analyzed",
            "已保存的测试解读",
            "old-analysis",
        )
        await session.commit()
        original_body, identifier = article.body, article.id
        next_payload = deepcopy(fetcher.payload)
        next_payload["downloads"] = 999
        same = ModelFetcher(next_payload)
        collector = HuggingFaceCollector(same)
        collector.known_cards = {next_payload["id"]: article.metrics["model"]}
        repeat = await collector.collect(source)
        assert len(same.calls) == 1 and repeat.items[0].metrics["model"]["card_status"] == "cached"
        repeated, outcome = await ingest(session, source, repeat.items[0])
        await session.commit()
        assert outcome == "duplicates" and repeated.id == identifier
        assert repeated.body == original_body and repeated.analysis_hash == "old-analysis"
        assert repeated.metrics["model"]["code_url"] == "https://github.com/fixture/coder"
        assert repeated.published_at is None and repeated.metrics["downloads"] == 999
        assert activity_time(repeated) != repeated.collected_at
        next_payload["sha"] = "b" * 40
        failed = await HuggingFaceCollector(
            ModelFetcher(next_payload, FetchError("secret response", 403))
        ).collect(source)
        assert failed.items and failed.errors and "secret response" not in str(failed.errors)
        repeated, outcome = await ingest(session, source, failed.items[0])
        await session.commit()
        assert repeated.body == original_body and repeated.status == "analyzed"
        assert repeated.metrics["model"]["card_status"] == "unavailable"
        assert repeated.metrics["model"]["card_revision"] == "a" * 40
        assert await session.scalar(select(func.count()).select_from(Article)) == 1
        assert await session.scalar(select(func.count()).select_from(RawRecord)) == 3


async def test_identical_metadata_does_not_merge_different_model_ids(database):
    db, _ = database
    async with db.sessions() as session:
        source = Source(
            id="model-identity",
            name="Models",
            kind="hf_models",
            url="https://huggingface.co/api/models",
        )
        session.add(source)
        await session.flush()
        for identifier in ["fixture/model-one", "fixture/model-two"]:
            article, outcome = await ingest(
                session,
                source,
                RawItem(
                    platform_id=identifier,
                    title="Same model description",
                    body="Training benchmark implementation " * 10,
                    url=f"https://huggingface.co/{identifier}",
                    metrics={"kind": "model", "model": model_metadata(model_payload(identifier))},
                ),
            )
            assert outcome == "added"
            await link_related(session, article)
        await session.commit()
        assert await session.scalar(select(func.count()).select_from(Article)) == 2
        assert await session.scalar(select(func.count()).select_from(ArticleLink)) == 0


async def test_query_failure_advances_and_does_not_discard_other_groups():
    class PartialFetcher(ModelFetcher):
        settings = Settings(hf_queries_per_run=3, hf_card_checks=0, _env_file=None)

        async def json(self, url):
            query = parse_qs(urlsplit(url).query)
            if "pipeline_tag" in query and "author" not in query:
                raise FetchError("private service body", 429)
            return [model_payload("openai/fixture-model")]

    source = Source(kind="hf_models", config={}, cursor={})
    result = await HuggingFaceCollector(PartialFetcher()).collect(source)
    assert result.errors and result.items and result.advance_on_partial
    assert result.cursor["model_tick"] == 3
    assert result.cursor["scans"]["topic:llm:text-generation"]["status"] == "failed"
    assert result.cursor["scans"]["publisher:zai"]["status"] == "success"
    assert "private service body" not in str(result.errors)


def test_official_model_phase_is_a_claim_and_update_only_date_is_not_release_date():
    source = Source(
        kind="rss",
        trust="official",
        config={"publisher_id": "google"},
        url="https://blog.google/technology/ai/rss/",
    )
    item = RawItem(
        title="Introducing Gemini 4 preview",
        body='Technical model report <a href="https://huggingface.co/google/fixture">Weights</a>',
        published_at=now(),
        metrics={"feed_time_kind": "updated"},
    )
    annotate_official_model(item, source)
    assert item.metrics["kind"] == "model_release"
    assert item.metrics["model"]["release_status"] == "preview"
    assert item.metrics["model"]["release_at"] is None
    assert item.metrics["model"]["references"] == ["google/fixture"]
    assert item.metrics["model"]["access"] == "unknown"
    news = RawItem(
        title="Quarterly earnings and cloud partnerships", body="New model customer adoption"
    )
    annotate_official_model(news, source)
    assert "model" not in news.metrics


async def test_model_api_filters_links_and_new_release_without_stars(client, database):
    db, _ = database
    async with db.sessions() as session:
        source = await session.get(Source, "hf-models")
        payload = model_payload()
        model = model_metadata(payload)
        record, _ = await ingest(
            session,
            source,
            RawItem(
                platform_id=payload["id"],
                title=payload["id"],
                body="Code generation model with reproducible training implementation and benchmark",
                url=model["card_url"],
                metrics={"kind": "model", "model": model, "downloads": 0},
            ),
        )
        official = await session.get(Source, "google-ai")
        notice = RawItem(
            platform_id="notice",
            title="Introducing new code model",
            body=f'A technical model release with training and benchmark implementation. <a href="{model["card_url"]}">Model</a>',
            published_at=now(),
        )
        annotate_official_model(notice, official)
        report, _ = await ingest(session, official, notice)
        await link_related(session, report)
        await session.commit()
        assert (
            await session.scalar(
                select(func.count())
                .select_from(ArticleLink)
                .where(ArticleLink.method == "model_reference")
            )
            == 1
        )
        first_rank = article_rank(record, now(), ["coding_models"], include_heat=False)[0]
        record.metrics = {**record.metrics, "downloads": 999999, "likes": 999999}
        assert (
            abs(article_rank(record, now(), ["coding_models"], include_heat=False)[0] - first_rank)
            < 0.01
        )
    all_models = (await client.get("/api/articles?content_type=models")).json()
    assert all_models["total"] == 2
    filtered = (
        await client.get("/api/articles?content_type=models&publisher=qwen&topic=coding_models")
    ).json()
    assert filtered["total"] == 1 and filtered["items"][0]["id"] == record.id
    assert (await client.get("/api/articles?topic=unknown")).status_code == 422
    assert (await client.get("/api/articles?publisher=unknown")).status_code == 422
    dashboard = (await client.get("/api/recommendations")).json()
    models = next(section for section in dashboard["sections"] if section["id"] == "models")
    assert len(models["items"]) == 1
    assert models["items"][0]["article"]["metrics"]["kind"] in {"model", "model_release"}


async def test_metric_refresh_does_not_make_old_model_a_new_release(client, database):
    db, _ = database
    async with db.sessions() as session:
        source = await session.get(Source, "hf-models")
        payload = model_payload()
        payload["lastModified"] = (now() - timedelta(days=400)).isoformat()
        model = model_metadata(payload)
        item = RawItem(
            platform_id=payload["id"],
            title=payload["id"],
            body="Training implementation benchmark for code generation " * 5,
            metrics={"kind": "model", "model": model, "downloads": 500},
        )
        record, _ = await ingest(session, source, item)
        await session.commit()
        item.metrics["downloads"] = 1000
        await ingest(session, source, item)
        await session.commit()
        assert record.updated_at > now() - timedelta(minutes=1)
    dashboard = (await client.get("/api/recommendations")).json()
    assert (
        next(section for section in dashboard["sections"] if section["id"] == "models")["items"]
        == []
    )
