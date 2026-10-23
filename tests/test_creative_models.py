from copy import deepcopy

import pytest
from frontiersignal.collectors.huggingface import HuggingFaceCollector, model_groups, model_query
from frontiersignal.config import Settings
from frontiersignal.model_info import (
    MODEL_TASKS,
    annotate_official_model,
    attach_model_card,
    model_metadata,
    specification_quotes,
)
from frontiersignal.models import Source, now
from frontiersignal.normalizer import RawItem
from frontiersignal.storage import ingest
from frontiersignal.technical import technical_signal
from frontiersignal.topics import CATALOG, collection_topics


def payload(task, identifier="fixture/creative-model"):
    return {
        "id": identifier,
        "sha": "b" * 40,
        "pipeline_tag": task,
        "tags": [task],
        "siblings": [{"rfilename": "README.md"}, {"rfilename": "model.safetensors"}],
        "gated": False,
        "lastModified": now().isoformat(),
    }


@pytest.mark.parametrize(
    "topic,task",
    [(topic, task) for topic in ("image", "video", "audio") for task in CATALOG[topic].hf_tasks],
)
def test_creative_task_metadata_and_screening_do_not_require_llm_keywords(topic, task):
    metadata = model_metadata(payload(task))
    assert topic in metadata["topics"]
    assert metadata["task_label"] == MODEL_TASKS[task][0]
    assert metadata["modalities"]["basis"] == task
    assert metadata["modalities"]["outputs"] == list(MODEL_TASKS[task][2])
    assert metadata["specifications"] == [] and metadata["release_at"] is None
    signal = technical_signal("fixture/creative-model", "", "hf_models", {"model": metadata})
    assert signal.eligible and "llm" not in signal.topics


def test_topic_fairness_query_coverage_and_publisher_scope_remain_bounded():
    source = Source(kind="hf_models", config={})
    topics = collection_topics("hf_models")
    first = [
        group["topics"][0]
        for tick in range(len(topics) * 6)
        if (group := model_query(source, tick, 5)[0])["lane"] == "topic"
    ][: len(topics)]
    assert first == topics
    queries = [model_query(source, tick, 5) for tick in range(3 * len(topics) * 7 * 3)]
    assert {group["id"] for group, _ in queries} == {group["id"] for group in model_groups(source)}
    for group in model_groups(source):
        if group["lane"] == "topic":
            assert {
                params["sort"] for candidate, params in queries if candidate["id"] == group["id"]
            } == {"createdAt", "lastModified", "trendingScore"}
    for group, params in queries:
        assert params["limit"] == 5
        if group["lane"] == "publisher":
            assert "pipeline_tag" not in params
    audio = Source(kind="hf_models", config={"discovery_topics": ["audio"]})
    groups = model_groups(audio)
    assert all(group["topics"] == ["audio"] for group in groups)
    assert "publisher:bfl" not in {group["id"] for group in groups}
    assert "publisher:acestep" in {group["id"] for group in groups}


def test_specs_keep_qualifiers_and_revision_instead_of_inventing_maximum_capabilities():
    metadata = model_metadata(payload("text-to-video"))
    metadata["card_revision"] = "b" * 40
    body = """# A fixture video model
The example uses 720p resolution, not a maximum supported resolution.
This example generates 5 seconds at 24 fps.
An RTX 4090 with 24 GB VRAM is recommended for this configuration.
Streaming is not supported in this release.
```python
sample_rate = "999 kHz"
```
"""
    attach_model_card(metadata, body)
    quotes = {row["kind"]: row for row in metadata["specifications"]}
    assert "not a maximum" in quotes["resolution"]["text"]
    assert "example" in quotes["duration"]["text"]
    assert "not supported" in quotes["streaming"]["text"]
    assert "sample_rate" not in quotes
    assert all(row["revision"] == "b" * 40 for row in quotes.values())
    assert all("/blob/" in row["source_url"] for row in quotes.values())
    assert len(specification_quotes(body * 100, metadata["card_url"])) <= 6
    assert specification_quotes(body, "javascript:alert(1)") == []
    metadata_header = "---\nbase_model: fixture/asr-streaming\ntags:\n- 1080p\n---\n"
    quoted = specification_quotes(
        "模型仓库：fixture/model\n" + metadata_header + body, metadata["card_url"]
    )
    assert all("base_model" not in row["text"] and "1080p" not in row["text"] for row in quoted)
    assert (
        next(row for row in quoted if row["kind"] == "streaming")["text"]
        == "Streaming is not supported in this release."
    )
    unknown = model_metadata(payload("custom-audio-task"))
    assert unknown["modalities"] is None and unknown["task_label"] is None


def test_verified_publisher_family_retains_tagless_models_without_guessing_their_task():
    data = payload(None, "Wan-AI/Wan2.2-Animate-2-14B")
    data["tags"] = ["diffusers", "safetensors"]
    model = model_metadata(data)
    assert model["topics"] == ["video"] and model["publisher_verified"]
    assert model["task"] is None and model["modalities"] is None
    data["id"] = "unverified/Wan2.2-Animate-copy"
    unverified = model_metadata(data)
    assert not unverified["publisher_verified"] and unverified["topics"] == []


async def test_creative_card_evidence_survives_metadata_only_refresh(database):
    db, _ = database
    async with db.sessions() as session:
        source = Source(
            id="creative", name="Models", kind="hf_models", url="https://huggingface.co/api/models"
        )
        session.add(source)
        await session.flush()
        data = payload("text-to-audio")
        model = model_metadata(data)
        model.update(card_revision=data["sha"], card_status="available")
        body = "The model generates stereo audio at 44.1 kHz.\nThe example requires 8 GB VRAM."
        attach_model_card(model, body)
        item = RawItem(
            platform_id=data["id"],
            title=data["id"],
            body=body,
            metrics={"kind": "model", "model": model},
        )
        article, _ = await ingest(session, source, item)
        article.status, article.summary_zh = "analyzed", "已保存的音频模型解读"
        await session.commit()
        identifier = article.id
        update = RawItem(
            platform_id=data["id"],
            title=data["id"],
            body="Metadata only",
            preserve_existing_content=True,
            metrics={"kind": "model", "model": model_metadata(data)},
        )
        refreshed, outcome = await ingest(session, source, update)
        assert refreshed.id == identifier and outcome == "duplicates"
        assert refreshed.body == body and refreshed.summary_zh == "已保存的音频模型解读"
        assert refreshed.metrics["model"]["specifications"] == model["specifications"]


async def test_keyword_queries_reject_other_topic_results_and_never_download_weights():
    class Fetcher:
        settings = Settings(hf_queries_per_run=1, hf_card_checks=1, _env_file=None)

        async def json(self, url):
            assert "pipeline_tag=text-to-image" in url
            return [payload("text-generation", "fixture/wrong-task"), payload("text-to-image")]

        async def get(self, url):
            assert url.endswith("/README.md")
            return b"This diffusion implementation supports 1024x1024 resolution.", {}, 200

    source = Source(
        kind="hf_models", config={"discovery_topics": ["image", "llm"]}, cursor={"model_tick": 3}
    )
    # Topic order follows the stable catalog: cycle 1 selects image.
    result = await HuggingFaceCollector(Fetcher()).collect(source)
    assert not result.errors and result.filtered == 1 and len(result.items) == 1
    assert result.items[0].metrics["model"]["topics"] == ["image"]
    assert result.items[0].metrics["model"]["specifications"]


@pytest.mark.parametrize(
    "publisher,title,topic",
    [
        ("google", "Introducing Veo 4 preview", "video"),
        ("openai", "Sora is now available", "video"),
        ("google", "Introducing Imagen 5", "image"),
        ("qwen", "Introducing Qwen3-TTS", "audio"),
    ],
)
def test_official_creative_model_announcements_are_not_forced_into_llm(publisher, title, topic):
    source = Source(
        kind="rss",
        trust="official",
        config={"publisher_id": publisher},
        url="https://blog.google/technology/ai/rss/",
    )
    item = RawItem(
        title=title,
        body="Technical report and implementation.",
        url="https://blog.google/fixture",
        published_at=now(),
        metrics={"feed_time_kind": "published"},
    )
    annotate_official_model(item, source)
    assert item.metrics["kind"] == "model_release"
    assert topic in item.metrics["model"]["topics"]
    assert "llm" not in item.metrics["model"]["topics"]
    assert item.metrics["model"]["release_at"] == item.published_at.isoformat()


def test_entertainment_outputs_and_non_ai_editing_are_not_technical_model_news():
    for title, body in [
        ("Image editing tips for vacation photos", "A basic photo editor tutorial with no AI."),
        ("New music album and celebrity concert", "Music videos and entertainment giveaways."),
        ("Video editing keyboard shortcuts", "Implementation of timeline keyboard controls."),
    ]:
        assert not technical_signal(title, body, "hackernews").eligible
    assert technical_signal(
        "A diffusion model for music generation",
        "Neural architecture, training code and benchmark paper with reproducible inference.",
        "hackernews",
    ).eligible


async def test_creative_models_roundtrip_filters_and_preserve_reading_state(client, database):
    db, _ = database
    originals = {}
    async with db.sessions() as session:
        source = await session.get(Source, "hf-models")
        for topic, task in [
            ("image", "text-to-image"),
            ("video", "image-to-video"),
            ("audio", "text-to-speech"),
        ]:
            data = payload(task, f"fixture/{topic}")
            model = model_metadata(data)
            item = RawItem(
                platform_id=data["id"],
                title=data["id"],
                body="Open neural model weights and reproducible training implementation.",
                url=model["card_url"],
                raw=deepcopy(data),
                metrics={"kind": "model", "model": model},
            )
            article, _ = await ingest(session, source, item)
            article.is_favorite = article.is_read = True
            originals[topic] = article.id
        await session.commit()
    for topic, identifier in originals.items():
        result = (
            await client.get(f"/api/articles?content_type=models&topic={topic}&technical=true")
        ).json()
        assert result["total"] == 1 and result["items"][0]["id"] == identifier
        assert result["items"][0]["is_read"] and result["items"][0]["is_favorite"]
    preferences = (await client.get("/api/settings")).json()["interest_topics"]
    response = await client.patch(
        "/api/sources/hf-models", json={"discovery_topics": ["image", "video", "audio"]}
    )
    assert response.status_code == 200
    assert (await client.get("/api/settings")).json()["interest_topics"] == preferences
