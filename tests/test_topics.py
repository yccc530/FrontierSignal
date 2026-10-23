from frontiersignal.collectors.github_discovery import GitHubDiscoveryCollector
from frontiersignal.config import Settings
from frontiersignal.models import Source
from frontiersignal.topics import CATALOG, LEGACY_TOPICS, collection_topics


async def test_historical_reclassification_preview_and_apply_preserve_reading_and_analysis(
    database, monkeypatch, capsys
):
    import importlib.util
    from pathlib import Path

    from frontiersignal.models import Article, RawRecord
    from frontiersignal.normalizer import RawItem
    from frontiersignal.storage import ingest
    from sqlalchemy import func, select

    db, settings = database
    async with db.sessions() as session:
        source = Source(
            id="historical",
            name="Historical model",
            kind="hf_models",
            url="https://huggingface.co/api/models",
        )
        session.add(source)
        await session.flush()
        item = RawItem(
            platform_id="fixture/coder",
            title="fixture/coder",
            body="Code generation training implementation with benchmark",
            raw={
                "id": "fixture/coder",
                "pipeline_tag": "text-generation",
                "tags": ["code-generation"],
                "createdAt": "2025-01-01T00:00:00Z",
            },
        )
        row, _ = await ingest(session, source, item)
        row.technical_topics, row.technical_score, row.technical_eligible = [], 0, False
        row.is_read = row.is_favorite = True
        row.status, row.analysis_hash, row.summary_zh = (
            "analyzed",
            "keep-analysis",
            "已保存的中文摘要",
        )
        await session.commit()
        identifier, original_body, original_hash = row.id, row.body, row.content_hash
    path = Path(__file__).resolve().parents[1] / "scripts/backfill_technical.py"
    spec = importlib.util.spec_from_file_location("backfill_for_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "settings", settings)
    await module.main()
    async with db.sessions() as session:
        preview = await session.get(Article, identifier)
        assert preview.technical_topics == [] and "model" not in preview.metrics
    await module.main(apply=True)
    async with db.sessions() as session:
        updated = await session.get(Article, identifier)
        assert "coding_models" in updated.technical_topics
        assert updated.body == original_body and updated.content_hash == original_hash
        assert updated.is_read and updated.is_favorite
        assert updated.status == "analyzed" and updated.analysis_hash == "keep-analysis"
        assert updated.summary_zh == "已保存的中文摘要"
        assert await session.scalar(select(func.count()).select_from(RawRecord)) == 1
    capsys.readouterr()
    await module.main()
    assert "'changed': 0" in capsys.readouterr().out


async def test_all_registered_preferences_roundtrip_without_resetting_existing(
    client, monkeypatch, tmp_path
):
    monkeypatch.setattr("frontiersignal.discovery_api.PROJECT_ROOT", tmp_path)
    before = (await client.get("/api/settings")).json()["interest_topics"]
    assert before == list(LEGACY_TOPICS)
    topics = (await client.get("/api/topics")).json()
    assert len(topics) == len(CATALOG) > 8
    assert next(row for row in topics if row["id"] == "3d")["discovery_ready"] is True
    assert next(row for row in topics if row["id"] == "video")["discovery_ready"] is True
    values = list(CATALOG)
    assert (await client.patch("/api/preferences", json={"topics": values})).status_code == 200
    assert (await client.get("/api/settings")).json()["interest_topics"] == values
    assert Settings(_env_file=tmp_path / ".env").interest_topics == values
    assert (
        await client.patch("/api/preferences", json={"topics": ["llm", "llm"]})
    ).status_code == 422
    assert (await client.patch("/api/preferences", json={"topics": ["unknown"]})).status_code == 422


async def test_source_collection_scope_is_independent_from_preferences(client):
    before = (await client.get("/api/settings")).json()["interest_topics"]
    path = "/api/sources/github-discovery"
    assert (await client.patch(path, json={"discovery_topics": ["ocr"]})).status_code == 200
    sources = (await client.get("/api/sources")).json()
    assert next(row for row in sources if row["id"] == "github-discovery")["discovery_topics"] == [
        "ocr"
    ]
    assert (await client.get("/api/settings")).json()["interest_topics"] == before
    for invalid in [[], ["llm", "llm"], ["unknown"]]:
        assert (await client.patch(path, json={"discovery_topics": invalid})).status_code == 422
    assert (
        await client.patch("/api/sources/openai", json={"discovery_topics": ["llm"]})
    ).status_code == 422
    reset = (await client.patch(path, json={"discovery_topics": None})).json()
    assert reset["discovery_topics"] == collection_topics("github_discovery")


async def test_unscanned_groups_are_not_marked_success(client):
    coverage = (await client.get("/api/discovery/coverage")).json()
    groups = next(row for row in coverage["sources"] if row["source_id"] == "github-discovery")[
        "groups"
    ]
    assert len(groups) == len(collection_topics("github_discovery"))
    assert all(row["status"] == "pending" and row["last_scan_at"] is None for row in groups)


async def test_bounded_github_rotation_preserves_success_and_advances_after_failure():
    class Fetcher:
        settings = Settings(github_queries_per_run=1, _env_file=None)

        async def json(self, url, headers):
            if "topic%3Allm" in url:
                raise ValueError("network diagnostic not for users")
            return {"items": []}

    source = Source(kind="github_discovery", config={"discovery_topics": ["llm", "ocr"]}, cursor={})
    first = await GitHubDiscoveryCollector(Fetcher()).collect(source)
    assert first.errors and first.cursor["scans"]["llm"]["status"] == "failed"
    source.cursor = first.cursor
    second = await GitHubDiscoveryCollector(Fetcher()).collect(source)
    assert not second.errors
    assert second.cursor["scans"]["ocr"]["status"] == "success"
    assert second.cursor["scans"]["ocr"]["candidates"] == 0
    assert second.cursor["scans"]["llm"]["last_success_at"] is None
    assert second.cursor["discovery_tick"] == 2
