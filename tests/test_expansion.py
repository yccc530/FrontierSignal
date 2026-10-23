import pytest
from frontiersignal.content_info import content_metadata
from frontiersignal.model_info import model_metadata, specification_quotes
from frontiersignal.technical import technical_signal
from frontiersignal.topics import collection_topics


@pytest.mark.parametrize(
    "identifier,task,tags,topic",
    [
        ("tencent/Hunyuan3D-2.1", "image-to-3d", [], "3d"),
        ("fixture/Text2CAD", None, ["text-to-cad"], "cad"),
        ("fixture/world-model", None, ["world-model"], "world_models"),
        ("openvla/openvla-7b", "robotics", [], "robotics"),
    ],
)
def test_spatial_discovery_with_and_without_pipeline(identifier, task, tags, topic):
    model = model_metadata({"id": identifier, "pipeline_tag": task, "tags": tags})
    assert topic in model["topics"]
    assert topic in collection_topics("hf_models")
    assert topic in collection_topics("github_discovery")
    if task in {None, "robotics"}:
        assert model["modalities"] is None


def test_spatial_evidence_does_not_confuse_mesh_and_editable_cad():
    quotes = specification_quotes(
        "Outputs GLB meshes, not editable parametric CAD.\n"
        "Only evaluated in MuJoCo simulation; no real robot hardware experiments.",
        "https://huggingface.co/fixture/model",
    )
    assert {row["kind"] for row in quotes} >= {"output_format", "editability", "simulation"}
    assert "not editable" in next(row["text"] for row in quotes if row["kind"] == "editability")
    assert not technical_signal(
        "Editable CAD models", "Parametric geometry for mechanical design software", "github"
    ).eligible


def test_vibe_declaration_requires_readme_and_does_not_exclude_real_games():
    metrics = {"kind": "repository", "language": "TypeScript", "resource": {"readme_sha": "a" * 40}}
    body = "This browser game was built with AI. Open source code with neural inference benchmark."
    meta = content_metadata(
        "Browser games",
        body,
        "github_discovery",
        metrics,
        "https://github.com/fixture/game",
        readme=body,
    )
    assert meta["resource"]["type"] == "project"
    assert meta["resource"]["vibe_status"] == "author_declared"
    assert not meta["resource"]["execution_verified"]
    assert technical_signal("Browser games", body, "github_discovery", meta).eligible
    no_proof = content_metadata(
        "Vibe coded", body, "github_discovery", {}, "https://github.com/f/a"
    )
    assert no_proof["resource"]["vibe_status"] == "unverified"
    assert (
        "vibe_projects"
        not in technical_signal("Vibe coded", body, "github_discovery", no_proof).topics
    )
    negative = content_metadata(
        "Game",
        "",
        "github_discovery",
        metrics,
        "https://github.com/f/a",
        readme="This project was not built with AI.",
    )
    assert negative["resource"]["vibe_status"] == "unverified"
    assert not technical_signal(
        "Celebrity game giveaway", "discount coupon marketing", "github"
    ).eligible


@pytest.mark.parametrize(
    "body,expected",
    [
        ("An AI coding assistant for your code editor", "tool"),
        ("ComfyUI generative workflow with image inputs and video outputs", "workflow"),
    ],
)
def test_resource_kinds_are_separate(body, expected):
    result = content_metadata("fixture", body, "github_discovery", {}, "https://github.com/f/a")
    assert result["resource"]["type"] == expected


@pytest.mark.parametrize(
    "body,expected",
    [
        ("MCP server for Claude Desktop. Requires OAuth permission to read documents.", "plugin"),
        ("A runtime framework and SDK for AI agents", "framework"),
        ("A local LLM desktop client", "client"),
        ("AI research assistant for a local knowledge base", "application"),
        ("LLM observability and AI testing tool", "tool"),
    ],
)
def test_toolchain_types_and_declarations(body, expected):
    result = content_metadata(
        "fixture",
        body,
        "github_discovery",
        {"resource": {"readme_sha": "b" * 40}},
        "https://github.com/f/a",
        readme=body,
    )
    assert result["resource"]["type"] == expected
    if expected == "plugin":
        assert {q["kind"] for q in result["resource"]["quotes"]} >= {"host", "authorization"}


def test_generic_agent_or_knowledge_base_is_not_sufficient_technical_evidence():
    assert not technical_signal(
        "AI agent", "Your amazing personal assistant", "github_discovery"
    ).eligible
    assert not technical_signal(
        "Knowledge base", "Office knowledge base software", "github_discovery"
    ).eligible


@pytest.mark.parametrize(
    "title,body,topic",
    [
        (
            "Neural operator for fluid simulation",
            "We propose a physics informed neural architecture and training benchmark.",
            "scientific",
        ),
        (
            "Neural theorem proving",
            "We evaluate mathematical reasoning with language models and open code.",
            "math",
        ),
        (
            "Materials discovery",
            "We present a neural diffusion model with experiments on crystal generation benchmarks.",
            "materials",
        ),
        (
            "Protein structure prediction",
            "We propose a deep learning architecture with training code and a benchmark.",
            "biology",
        ),
    ],
)
def test_scientific_topics_require_ai_evidence(title, body, topic):
    signal = technical_signal(title, body, "arxiv")
    assert signal.eligible and topic in signal.topics
    meta = content_metadata(title, body, "arxiv", {}, "https://arxiv.org/abs/2610.12345v2")
    assert meta["research"]["independent_replication"] == "unknown"
    assert meta["identity_refs"] == ["paper:2610.12345"]


@pytest.mark.parametrize(
    "title",
    [
        "Theorem proving with pencil and paper",
        "Materials discovery in an ancient mine",
        "Protein structure prediction from manual observations",
    ],
)
def test_generic_scientific_subject_is_not_ai_news(title):
    assert not technical_signal(title, "Experiments and benchmark measurements.", "arxiv").eligible


def test_paper_links_keep_model_dataset_and_code_identity_separate():
    meta = content_metadata(
        "Research",
        "We propose a neural operator. Code is available at https://github.com/team/solver.\n"
        "https://huggingface.co/team/model\nhttps://huggingface.co/datasets/team/data",
        "arxiv",
        {},
        "https://arxiv.org/abs/2610.12345",
    )
    assert {r["kind"] for r in meta["references"]} == {"model", "dataset", "code"}
    assert "claim" in {q["kind"] for q in meta["research"]["quotes"]}


def test_observation_requires_real_samples_for_complete_day():
    from datetime import timedelta
    from types import SimpleNamespace

    from frontiersignal.models import now
    from frontiersignal.observability import observation_window

    at = now()
    samples = [
        SimpleNamespace(observed_at=at - timedelta(minutes=5 * i), scheduler_enabled=True)
        for i in range(289)
    ]
    assert observation_window(samples, at)["status"] == "covered"
    assert observation_window(samples[:20], at)["status"] == "pending"
    assert observation_window(samples[:10] + samples[20:], at)["status"] == "gaps"
    assert observation_window(samples, at)["seven_day_status"] == "pending"


async def test_recommendation_policy_exposure_and_real_updates(client, database):
    from frontiersignal.models import Article, Source, now
    from frontiersignal.normalizer import RawItem
    from frontiersignal.storage import ingest

    db, _ = database
    async with db.sessions() as session:
        source = await session.get(Source, "hf-models")
        for index in range(8):
            topic = "image" if index < 4 else "audio"
            item = RawItem(
                platform_id=f"fixture/model-{index}",
                title=f"fixture/model-{index}",
                body=f"Neural architecture training code and benchmark paper {index}",
                url=f"https://huggingface.co/fixture/model-{index}",
                metrics={
                    "kind": "model",
                    "model": {
                        "id": f"fixture/model-{index}",
                        "topics": [topic],
                        "revision": "a" * 40,
                        "hub_updated_at": now().isoformat(),
                    },
                },
            )
            await ingest(session, source, item)
        await session.commit()
    policy = (await client.get("/api/recommendation-policy")).json()
    policy["section_limits"].update({"models": 4, "discoveries": 0})
    policy["topic_weights"] = {"image": 3, "audio": 1}
    assert (await client.patch("/api/recommendation-policy", json=policy)).status_code == 200
    assert (
        await client.patch("/api/recommendation-policy", json={"topic_weights": {"fake": 5}})
    ).status_code == 422
    dashboard = (await client.get("/api/recommendations")).json()
    models = next(s["items"] for s in dashboard["sections"] if s["id"] == "models")
    assert len(models) == 4
    assert sum("image" in row["article"]["technical_topics"] for row in models) == 3
    assert not next(s["items"] for s in dashboard["sections"] if s["id"] == "discoveries")
    first = models[0]
    payload = {
        "items": [
            {
                "article_id": first["article"]["id"],
                "revision_hash": first["exposure"]["revision_hash"],
            }
        ]
    }
    assert (await client.post("/api/recommendations/seen", json=payload)).json()["recorded"] == 1
    from frontiersignal.recommendation_state import exposure_state

    async with db.sessions() as session:
        article = await session.get(Article, first["article"]["id"])
        article.metrics = {**article.metrics, "downloads": 99999}
        assert (await exposure_state(session, [article], now(), 24))[article.id][
            "status"
        ] == "unchanged"
        article.metrics = {
            **article.metrics,
            "model": {**article.metrics["model"], "revision": "b" * 40},
        }
        assert (await exposure_state(session, [article], now(), 24))[article.id][
            "status"
        ] == "updated"
        await session.commit()
    assert (await client.post("/api/recommendations/seen", json=payload)).json()["recorded"] == 0


async def test_explicit_paper_model_relation_keeps_independent_records(database):
    from frontiersignal.models import ArticleLink, Source
    from frontiersignal.normalizer import RawItem
    from frontiersignal.similarity import link_related
    from frontiersignal.storage import ingest
    from sqlalchemy import select

    db, _ = database
    async with db.sessions() as session:
        source = Source(
            id="test-model",
            name="Models",
            kind="hf_models",
            url="https://huggingface.co/api/models",
        )
        papers = Source(
            id="test-paper", name="Papers", kind="arxiv", url="https://export.arxiv.org/api/query"
        )
        session.add_all([source, papers])
        await session.flush()
        model, _ = await ingest(
            session,
            source,
            RawItem(
                title="A neural model",
                platform_id="f/a",
                url="https://huggingface.co/f/a",
                body="Implementation https://arxiv.org/abs/2610.12345",
            ),
        )
        paper, _ = await ingest(
            session,
            papers,
            RawItem(
                title="New neural architecture",
                url="https://arxiv.org/abs/2610.12345v2",
                body="We present a neural operator.",
            ),
        )
        await link_related(session, paper)
        link = await session.scalar(select(ArticleLink))
        assert link and link.method == "paper_reference"
        assert model.id != paper.id


async def test_narrowing_hf_scope_does_not_erase_other_query_history():
    from frontiersignal.collectors.huggingface import HuggingFaceCollector
    from frontiersignal.config import Settings
    from frontiersignal.models import Source

    class Fetcher:
        settings = Settings(hf_queries_per_run=1, hf_card_checks=0, _env_file=None)

        async def json(self, url):
            return []

    saved = {"status": "success", "last_success_at": "2026-10-22T12:00:00Z", "candidates": 4}
    source = Source(
        kind="hf_models",
        config={"discovery_topics": ["ocr"]},
        cursor={"scans": {"topic:video:text-to-video": saved}},
    )
    result = await HuggingFaceCollector(Fetcher()).collect(source)
    assert result.cursor["scans"]["topic:video:text-to-video"] == saved


def test_github_variants_include_skills_design_and_author_claims():
    from frontiersignal.collectors.github_discovery import topic_queries

    topics = ["mcp_skills", "ai_design", "vibe_projects"]
    queries = [q for tick in range(9) for q in topic_queries(topics, tick)]
    assert any('"agent skills"' in query for query in queries)
    assert any('"design-to-code"' in query for query in queries)
    assert any('"built with AI"' in query for query in queries)


async def test_explicit_model_dependencies_do_not_merge_distinct_models(database):
    from frontiersignal.models import ArticleLink, Source, now
    from frontiersignal.normalizer import RawItem
    from frontiersignal.recommendations import recommendation_dashboard
    from frontiersignal.similarity import rebuild_explicit_links
    from frontiersignal.storage import ingest
    from sqlalchemy import select

    db, _ = database
    async with db.sessions() as session:
        source = Source(
            id="models", name="Models", kind="hf_models", url="https://huggingface.co/api/models"
        )
        session.add(source)
        await session.flush()
        articles = []
        for name in ("base", "first", "second"):
            article, _ = await ingest(
                session,
                source,
                RawItem(
                    platform_id=f"fixture/{name}",
                    title=f"fixture/{name}",
                    url=f"https://huggingface.co/fixture/{name}",
                    body="Neural language model implementation, training and benchmark. "
                    + ("https://huggingface.co/fixture/base" if name != "base" else ""),
                    metrics={
                        "kind": "model",
                        "model": {
                            "id": f"fixture/{name}",
                            "topics": ["llm"],
                            "hub_updated_at": now().isoformat(),
                        },
                    },
                ),
            )
            articles.append(article)
        await session.flush()
        result = await rebuild_explicit_links(session, articles)
        assert result["matched_pairs"] == result["changed"] == 2
        assert (await rebuild_explicit_links(session, articles))["changed"] == 0
        links = (await session.scalars(select(ArticleLink))).all()
        assert len(links) == 2 and all(row.method == "model_reference" for row in links)
        dashboard = await recommendation_dashboard(session, now(), ["llm"])
        assert (
            len(
                next(
                    section["items"]
                    for section in dashboard["sections"]
                    if section["id"] == "models"
                )
            )
            == 3
        )
