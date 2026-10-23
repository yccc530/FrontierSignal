from datetime import UTC, datetime

from frontiersignal.models import Source
from frontiersignal.normalizer import RawItem
from frontiersignal.storage import ingest


async def seed(database):
    db, _ = database
    async with db.sessions() as session:
        source = await session.get(Source, "huggingface")
        first, _ = await ingest(
            session,
            source,
            RawItem(
                platform_id="a",
                title="AI model 50% better",
                body="中文模型原文",
                published_at=datetime(2026, 10, 21, tzinfo=UTC),
            ),
        )
        second, _ = await ingest(
            session,
            source,
            RawItem(
                platform_id="b",
                title="Other research",
                body="Unrelated text",
                published_at=datetime(2026, 10, 20, tzinfo=UTC),
            ),
        )
        first.category, first.score = "models", 90
        first.title_zh = "新一代智能模型进展"
        second.category, second.score = "research", 20
        await session.commit()
        return first.id, second.id


async def test_filters_search_sort_and_pagination(client, database):
    first, second = await seed(database)
    response = (await client.get("/api/articles", params={"q": "50%"})).json()
    assert response["total"] == 1 and response["items"][0]["id"] == first
    assert (await client.get("/api/articles", params={"q": "中文模型"})).json()["total"] == 1
    translated = (await client.get("/api/articles", params={"q": "新一代"})).json()
    assert translated["total"] == 1 and translated["items"][0]["title_zh"] == "新一代智能模型进展"
    assert (await client.get("/api/articles", params={"category": "research"})).json()["items"][0][
        "id"
    ] == second
    assert (await client.get("/api/articles", params={"after": "2026-10-21T00:00:00Z"})).json()[
        "total"
    ] == 1
    assert (
        await client.get("/api/articles", params={"sort": "score", "page_size": 1, "page": 2})
    ).json()["items"][0]["id"] == second
    assert (
        await client.get("/api/articles", params={"after": "2026-10-22", "before": "2026-10-20"})
    ).status_code == 422


async def test_favorite_read_details_and_raw_persist(client, database):
    first, _ = await seed(database)
    response = await client.patch(
        f"/api/articles/{first}", json={"is_read": True, "is_favorite": True}
    )
    assert response.status_code == 200
    data = (await client.get("/api/articles?favorite=true&read=true")).json()
    assert data["total"] == 1 and data["items"][0]["id"] == first
    details = (await client.get(f"/api/articles/{first}")).json()
    assert details["raw_versions"] == 1 and details["body"] == "中文模型原文"
    assert (await client.get(f"/api/articles/{first}/raw")).json()[0]["payload"][
        "body"
    ] == "中文模型原文"
    stats = (await client.get("/api/stats")).json()
    assert stats["favorites"] == 1 and stats["unread"] == 1


async def test_source_management_validation_and_disabled_trigger(client):
    assert (
        await client.patch("/api/sources/huggingface", json={"enabled": False})
    ).status_code == 200
    assert (await client.post("/api/sources/huggingface/collect")).status_code == 409
    assert (
        await client.patch("/api/sources/huggingface", json={"interval_minutes": 1})
    ).status_code == 422
    assert (
        await client.post(
            "/api/sources", json={"name": "Unsafe", "kind": "rss", "url": "https://127.0.0.1/"}
        )
    ).status_code == 422
    assert (
        await client.post(
            "/api/sources",
            json={
                "name": "Duplicate",
                "kind": "rss",
                "url": "https://huggingface.co/blog/feed.xml",
            },
        )
    ).status_code == 409


async def test_settings_write_is_private_and_validated(client, tmp_path, monkeypatch):
    monkeypatch.setattr("frontiersignal.settings_api.PROJECT_ROOT", tmp_path)
    original = (await client.get("/api/settings")).json()
    keys = [
        "llm_base_url",
        "llm_model",
        "llm_timeout",
        "llm_max_retries",
        "llm_batch_size",
        "llm_json_mode",
        "embedding_model",
    ]
    values = {key: original[key] for key in keys}
    values["llm_model"] = "test-config-model"
    assert (
        await client.patch("/api/settings", json={**values, "llm_api_key": "forbidden"})
    ).status_code == 422
    assert (
        await client.patch(
            "/api/settings", json={**values, "llm_base_url": "http://private.example"}
        )
    ).status_code == 422
    result = await client.patch("/api/settings", json=values)
    assert result.status_code == 200 and result.json()["llm_model"] == "test-config-model"
    content = (tmp_path / ".env").read_text()
    assert "test-config-model" in content and "forbidden" not in content


async def test_configurable_category(client):
    response = await client.post(
        "/api/categories", json={"id": "hardware", "label": "AI 硬件", "description": "算力与芯片"}
    )
    assert response.status_code == 201
    assert any(c["id"] == "hardware" for c in (await client.get("/api/categories")).json())


async def test_collect_without_enabled_sources_is_not_false_success(client):
    for source in (await client.get("/api/sources")).json():
        await client.patch(f"/api/sources/{source['id']}", json={"enabled": False})
    response = await client.post("/api/collect")
    assert response.status_code == 409
    assert (await client.get("/api/tasks")).json() == []
