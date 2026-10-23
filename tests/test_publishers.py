from copy import deepcopy
from urllib.parse import parse_qs, urlsplit

import pytest
from frontiersignal.collectors.huggingface import HuggingFaceCollector, model_groups, model_query
from frontiersignal.config import Settings
from frontiersignal.model_info import model_metadata
from frontiersignal.models import Source
from frontiersignal.network import FetchError
from frontiersignal.publishers import publisher_for_author
from frontiersignal.storage import ingest
from frontiersignal.technical import technical_signal


@pytest.mark.parametrize(
    "identifier,publisher,topic",
    [
        ("zai-org/GLM-4.5", "zai", "llm"),
        ("ZAI-ORG/GLM-4.6V", "zai", "multimodal"),
        ("zai-org/GLM-OCR", "zai", "ocr"),
        ("zai-org/GLM-TTS", "zai", "audio"),
        ("zai-org/CogVideoX-5b", "zai", "video"),
        ("meta-llama/Llama-4-Scout", "meta", "llm"),
        ("facebook/dinov3-vitb16", "meta", "multimodal"),
        ("facebook/sam3", "meta", "multimodal"),
        ("facebook/vjepa2-vitl", "meta", "world_models"),
        ("facebook/musicgen-small", "meta", "audio"),
    ],
)
def test_official_accounts_and_tagless_families_keep_unknown_capabilities(
    identifier, publisher, topic
):
    metadata = model_metadata({"id": identifier, "author": "untrusted-other-author"})
    assert metadata["publisher_id"] == publisher and metadata["publisher_verified"]
    assert topic in metadata["topics"]
    assert metadata["task"] is None and metadata["modalities"] is None
    assert metadata["release_at"] is None and metadata["access"] == "unknown"
    if identifier.startswith("facebook/"):
        assert "facebook/overview" in metadata["publisher_evidence"]


def test_community_models_and_statistical_glm_are_not_official_zai():
    assert publisher_for_author("THUDM") == (None, None)
    for author in ("community", "zai-org-copy", "facebookresearch-copy"):
        model = model_metadata({"id": f"{author}/GLM-4.5", "author": "zai-org"})
        assert model["publisher_id"] is None and not model["publisher_verified"]
    assert not technical_signal(
        "GLM regression tutorial", "Generalized linear models", "hackernews"
    ).eligible
    assert technical_signal(
        "GLM-4.5 training benchmark", "Model weights and reproducible implementation", "hackernews"
    ).eligible


def test_priority_rotation_stays_within_existing_budget_and_preserves_other_queries():
    source = Source(kind="hf_models", config={})
    priority = {group["id"] for group in model_groups(source) if group.get("priority")}
    assert priority == {"publisher:zai", "publisher:meta", "publisher:meta:facebook"}
    # Every pair of complete six-query runs covers all priority accounts, even after restart.
    for start in range(48):
        window = [model_query(source, tick, 5) for tick in range(start, start + 12)]
        assert priority <= {group["id"] for group, _ in window}
        assert all(params["limit"] == 5 for _, params in window)
    queries = [model_query(source, tick, 5) for tick in range(1800)]
    assert {group["id"] for group, _ in queries} == {group["id"] for group in model_groups(source)}
    assert {params["sort"] for group, params in queries if group.get("priority")} == {
        "createdAt",
        "lastModified",
    }
    scoped = Source(kind="hf_models", config={"discovery_topics": ["biology"]})
    assert not any(group.get("priority") for group in model_groups(scoped))
    assert all(model_query(scoped, tick, 5)[0]["topics"] == ["biology"] for tick in range(36))


async def test_priority_failure_cache_filter_and_saved_reading_state(client, database):
    class Fetcher:
        settings = Settings(hf_queries_per_run=6, hf_card_checks=2, _env_file=None)

        def __init__(self):
            self.calls = []
            self.fail_zai = False

        async def json(self, url):
            self.calls.append(url)
            author = parse_qs(urlsplit(url).query).get("author", [None])[0]
            if author not in {"zai-org", "meta-llama", "facebook"}:
                return []
            if author == "zai-org" and self.fail_zai:
                raise FetchError("secret diagnostic must not appear", 429)
            name = {"zai-org": "GLM-4.5", "meta-llama": "Llama-4", "facebook": "sam3"}[author]
            return [
                {
                    "id": f"{author}/{name}",
                    "sha": "a" * 40,
                    "siblings": [{"rfilename": "README.md"}],
                }
            ]

        async def get(self, url):
            self.calls.append(url)
            assert url.endswith("/README.md")
            return b"Model weights and reproducible training implementation.", {}, 200

    db, _ = database
    fetcher = Fetcher()
    source = Source(id="hf-models", kind="hf_models", config={}, cursor={})
    first = await HuggingFaceCollector(fetcher).collect(source)
    assert not first.errors and len(first.items) == 2 and len(fetcher.calls) == 8
    known = {}
    async with db.sessions() as session:
        stored_source = await session.get(Source, source.id)
        for item in first.items:
            article, _ = await ingest(session, stored_source, item)
            article.is_read = article.is_favorite = True
            article.summary_zh = "已有摘要"
            article.status = "analyzed"
            known[item.platform_id] = deepcopy(article.metrics["model"])
        await session.commit()
    fetcher.calls.clear()
    source.cursor = first.cursor
    second_collector = HuggingFaceCollector(fetcher)
    second_collector.known_cards = known
    second = await second_collector.collect(source)
    assert any(item.platform_id.startswith("facebook/") for item in second.items)
    assert sum(url.endswith("/README.md") for url in fetcher.calls) == 1
    async with db.sessions() as session:
        stored_source = await session.get(Source, source.id)
        for item in second.items:
            article, outcome = await ingest(session, stored_source, item)
            if item.platform_id in known:
                assert outcome == "duplicates"
                assert article.is_favorite and article.is_read and article.summary_zh == "已有摘要"
        await session.commit()
    for publisher, expected in (("zai", 1), ("meta", 2)):
        response = await client.get(f"/api/articles?content_type=models&publisher={publisher}")
        assert response.status_code == 200 and response.json()["total"] == expected
    fetcher.fail_zai = True
    source.cursor = {}
    partial = await HuggingFaceCollector(fetcher).collect(source)
    assert partial.errors and partial.items and partial.advance_on_partial
    assert partial.cursor["scans"]["publisher:zai"]["status"] == "failed"
    assert partial.cursor["scans"]["publisher:meta"]["status"] == "success"
    assert "secret diagnostic" not in str(partial.errors)
    coverage = (await client.get("/api/discovery/coverage")).json()
    hf = next(row for row in coverage["sources"] if row["source_id"] == "hf-models")
    assert hf["request_budget"] == 12 and hf["priority_scan_hours"] == 2
