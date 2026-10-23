import math
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select

from .models import Article, ArticleLink, Repository, StarSnapshot
from .momentum import project_momentum
from .normalizer import canonical_url
from .projects import parse_time, star_growth
from .recommendation_state import exposure_state, load_policy
from .schemas import ArticleOut
from .similarity import distinct_model_ids
from .topics import public_topics


def recency(value: datetime | None, at: datetime, half_life_hours: float) -> float:
    if value is None or value > at + timedelta(minutes=5):
        return 0.0
    hours = max(0.0, (at - value).total_seconds() / 3600)
    return 2 ** (-hours / half_life_hours)


def activity_time(article):
    if article.source.kind in {"hf_models", "hf_datasets"}:
        try:
            model = article.metrics.get("model") or {}
            return (
                parse_time(model.get("hub_updated_at") or article.metrics.get("updated_at"))
                or parse_time(model.get("hub_created_at"))
                or article.published_at
            )
        except (ValueError, TypeError):
            pass
    return article.published_at


def project_view(repository, article, snapshots, at, interests):
    growth24 = star_growth(snapshots, at, 1)
    growth7 = star_growth(snapshots, at, 7)
    momentum = project_momentum(repository, article, snapshots, at, interests)
    match = bool(set(article.technical_topics) & set(interests))
    reasons = momentum["reasons"] + list(article.technical_reasons[:2])
    if repository.has_code:
        reasons.append("官方目录 API 已发现代码文件，尚未运行验证")
    elif repository.language and repository.size_kb:
        reasons.append(f"仓库非空且标记 {repository.language}，实现质量仍需阅读核验")
    if match:
        reasons.append("匹配当前研究偏好")
    return {
        "id": repository.id,
        "article_id": article.id,
        "name": repository.full_name,
        "description": repository.description,
        "summary_zh": article.summary_zh,
        "url": repository.url,
        "language": repository.language,
        "license": repository.license,
        "topics": article.technical_topics,
        "stars": repository.stars,
        "forks": repository.forks,
        "growth_24h": growth24,
        "growth_7d": growth7,
        "momentum": {key: value for key, value in momentum.items() if key != "reasons"},
        "created_at": repository.created_at,
        "pushed_at": repository.pushed_at,
        "updated_at": repository.updated_at,
        "observed_at": repository.observed_at,
        "first_seen_at": repository.first_seen_at,
        "has_code": repository.has_code,
        "code_evidence": repository.code_evidence,
        "latest_release": repository.latest_release,
        "tracked": repository.tracked,
        "recommendation_score": momentum["score"],
        "reasons": reasons,
        "is_read": article.is_read,
        "is_favorite": article.is_favorite,
    }


async def ranked_projects(session, at, interests, topic=None, q=""):
    query = (
        select(Repository, Article)
        .join(Article, Repository.article_id == Article.id)
        .where(
            Article.technical_eligible.is_(True),
            Article.status != "filtered",
            Repository.archived.is_(False),
            Repository.tracked.is_(True),
        )
    )
    if q.strip():
        escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            (Repository.full_name.ilike(f"%{escaped}%", escape="\\"))
            | (Repository.description.ilike(f"%{escaped}%", escape="\\"))
        )
    rows = (await session.execute(query.order_by(Repository.observed_at.desc()).limit(1001))).all()
    truncated = len(rows) > 1000
    rows = rows[:1000]
    identifiers = [repo.id for repo, _ in rows]
    snapshots = (
        (
            await session.scalars(
                select(StarSnapshot).where(
                    StarSnapshot.repository_id.in_(identifiers),
                    StarSnapshot.observed_at >= at - timedelta(days=9),
                    StarSnapshot.observed_at <= at,
                )
            )
        ).all()
        if identifiers
        else []
    )
    history = {}
    for snapshot in snapshots:
        history.setdefault(snapshot.repository_id, []).append(snapshot)
    results = [
        project_view(repo, article, history.get(repo.id, []), at, interests)
        for repo, article in rows
        if not topic or topic in article.technical_topics
    ]
    results.sort(
        key=lambda row: (not row["momentum"]["is_rising"], -row["recommendation_score"], row["id"])
    )
    return results, truncated


def article_rank(article, at, interests, include_heat=True):
    score = article.technical_score * 0.5
    reasons = list(article.technical_reasons[:2])
    fresh = recency(
        activity_time(article), at, 24 if article.source.kind == "hackernews" else 7 * 24
    )
    score += 15 * fresh
    if set(article.technical_topics) & set(interests):
        score += 5
        reasons.append("匹配当前研究偏好")
    if article.score is not None and article.is_ai_related:
        score += min(10, article.score / 10)
    if article.source.trust == "official":
        score += 10
        reasons.append("官方原始发布，结论仍需独立验证")
    elif article.source.kind == "arxiv":
        score += 8 if len(article.body) >= 200 else 3
        reasons.append("提供论文摘要与作者信息；预印本不等于已验证结论")
    elif article.source.kind in {"github", "github_discovery", "hf_models", "hf_datasets"}:
        score += 6
        reasons.append("可追溯的代码、模型或数据资源")
    if article.source.kind == "hf_models":
        reasons.append("依据 Hub 仓库更新时间，非官方模型发布日期；热度不证明性能")
    if include_heat and article.source.kind == "hackernews":
        points = article.metrics.get("points")
        comments = article.metrics.get("comments_count")
        if isinstance(points, int) and points >= 0:
            score += min(25, math.log1p(points) * 3) * math.sqrt(fresh)
            reasons.append(
                f"HN {points} points"
                + (f"、{comments} 条评论" if isinstance(comments, int) else "")
            )
        if isinstance(comments, int) and comments >= 0:
            score += min(10, math.log1p(comments) * 2) * math.sqrt(fresh)
    if article.is_read:
        score -= 5
    return round(max(0, min(100, score)), 2), reasons


async def recommendation_dashboard(session, at, interests, topic=None):
    policy = await load_policy(session)
    projects, project_truncated = await ranked_projects(session, at, interests, topic)
    project_selection = [p for p in projects if p["momentum"]["is_rising"]][:6]
    selected_ids = {p["id"] for p in project_selection}
    emerging = [
        p
        for p in projects
        if p["momentum"]["is_new"]
        and p["id"] not in selected_ids
        and p["observed_at"] >= at - timedelta(hours=24)
    ][:4]
    query = (
        select(Article)
        .where(
            Article.technical_eligible.is_(True),
            Article.status != "filtered",
            or_(
                Article.published_at >= at - timedelta(days=30),
                Article.updated_at >= at - timedelta(days=30),
            ),
            func.coalesce(Article.published_at, Article.collected_at) <= at + timedelta(minutes=5),
        )
        .order_by(Article.technical_score.desc(), Article.published_at.desc())
        .limit(1001)
    )
    rows = list((await session.scalars(query)).all())
    truncated = len(rows) > 1000
    rows = [
        row
        for row in rows[:1000]
        if (not topic or topic in row.technical_topics)
        and (
            row.metrics.get("kind") != "repository"
            or row.id
            in {
                p["article_id"]
                for p in projects
                if p["momentum"]["is_new"] or p["momentum"]["is_rising"]
            }
        )
        and activity_time(row) is not None
        and at - timedelta(days=30) <= activity_time(row) <= at + timedelta(minutes=5)
    ]
    rows_by_id = {row.id: row for row in rows}
    links = (
        (
            await session.scalars(
                select(ArticleLink).where(
                    ArticleLink.left_id.in_(rows_by_id),
                    ArticleLink.right_id.in_(rows_by_id),
                    ArticleLink.method.in_(
                        [
                            "same_url",
                            "same_content",
                            "title_similarity",
                            "model_reference",
                            "paper_reference",
                        ]
                    ),
                    ArticleLink.similarity >= 0.96,
                )
            )
        ).all()
        if rows
        else []
    )
    neighbors = {}
    for link in links:
        if distinct_model_ids(rows_by_id[link.left_id], rows_by_id[link.right_id]):
            continue
        neighbors.setdefault(link.left_id, set()).add(link.right_id)
        neighbors.setdefault(link.right_id, set()).add(link.left_id)
    seen = {p["article_id"] for p in project_selection + emerging}
    urls = {canonical_url(p["url"]) for p in project_selection + emerging}
    model_ids = set()
    exposures = await exposure_state(session, rows, at, policy.repeat_hours)
    topic_counts = {}

    def choose(candidates, limit=6, heat=True):
        if limit <= 0:
            return []

        def fair_key(row):
            model_topics = (row.metrics.get("model") or {}).get("topics", [])
            explicit = [key for key in row.technical_topics if key in policy.topic_weights]
            topics = (
                [topic] if topic else explicit or model_topics or row.technical_topics or ["other"]
            )
            focus = min(
                topics,
                key=lambda key: (topic_counts.get(key, 0) / policy.topic_weights.get(key, 1), key),
            )
            return (
                exposures[row.id]["recent"],
                topic_counts.get(focus, 0) / policy.topic_weights.get(focus, 1),
                -article_rank(row, at, interests, heat)[0],
                row.id,
            ), focus

        ranked = list(candidates)
        selected = []
        while ranked:
            row = min(ranked, key=lambda row: fair_key(row)[0])
            ranked.remove(row)
            url = canonical_url(row.original_url)
            model_id = (row.metrics.get("model") or {}).get("id")
            model_id = model_id.casefold() if isinstance(model_id, str) else None
            if row.id in seen or (url and url in urls) or neighbors.get(row.id, set()) & seen:
                continue
            if model_id and model_id in model_ids:
                continue
            seen.add(row.id)
            focus = fair_key(row)[1]
            topic_counts[focus] = topic_counts.get(focus, 0) + 1
            if url:
                urls.add(url)
            if model_id:
                model_ids.add(model_id)
            score, reasons = article_rank(row, at, interests, heat)
            selected.append(
                {
                    "article": ArticleOut.model_validate(row).model_dump(),
                    "recommendation_score": score,
                    "reasons": reasons,
                    "related_count": len(neighbors.get(row.id, set())),
                    "exposure": exposures[row.id],
                }
            )
            if len(selected) >= limit:
                break
        return selected

    hn = [
        row
        for row in rows
        if row.source.kind == "hackernews"
        and row.published_at
        and row.published_at >= at - timedelta(hours=72)
    ]
    hot_limit = policy.section_limits["hot"]
    hot = choose(hn, limit=max(0, hot_limit - min(2, hot_limit)))
    fresh = choose(
        [row for row in hn if row.published_at >= at - timedelta(hours=12)],
        limit=min(2, hot_limit),
        heat=False,
    )
    hot += fresh
    if len(hot) < hot_limit:
        hot += choose(hn, limit=hot_limit - len(hot))
    papers = choose(
        [
            row
            for row in rows
            if row.source.kind == "arxiv"
            and row.published_at
            and row.published_at >= at - timedelta(days=14)
        ],
        limit=policy.section_limits["papers"],
    )
    models = choose(
        [row for row in rows if row.metrics.get("kind") in {"model", "model_release"}],
        limit=policy.section_limits["models"],
        heat=False,
    )
    tools = choose(
        [
            row
            for row in rows
            if (row.metrics.get("resource") or {}).get("type")
            in {"tool", "plugin", "framework", "client", "application"}
        ],
        limit=policy.section_limits["tools"],
        heat=False,
    )
    workflows = choose(
        [row for row in rows if (row.metrics.get("resource") or {}).get("type") == "workflow"],
        limit=policy.section_limits["workflows"],
        heat=False,
    )
    official = choose(
        [row for row in rows if row.source.trust == "official"],
        limit=policy.section_limits["official"],
    )
    discoveries = choose(
        [row for row in rows if row.metrics.get("kind") != "repository"],
        limit=policy.section_limits["discoveries"],
        heat=False,
    )
    return {
        "generated_at": at,
        "topics": public_topics(),
        "interests": interests,
        "policy": policy.model_dump(),
        "projects": project_selection,
        "emerging_projects": emerging,
        "sections": [
            {
                "id": "models",
                "title": "模型发布与更新",
                "window": "近 30 天 · 区分官方发布与模型仓库更新",
                "items": models,
            },
            {
                "id": "tools",
                "title": "开发工具与应用",
                "window": "近 30 天 · 新项目与增长异动",
                "items": tools,
            },
            {
                "id": "workflows",
                "title": "创作工作流",
                "window": "近 30 天 · 原文依赖与运行说明",
                "items": workflows,
            },
            {
                "id": "hot",
                "title": "今日 AI 技术热点",
                "window": "近 72 小时 · 保留新帖席位",
                "items": hot,
            },
            {
                "id": "papers",
                "title": "最新前沿论文",
                "window": "近 14 天 · AI、工程与科学研究",
                "items": papers,
            },
            {
                "id": "official",
                "title": "官方模型与技术发布",
                "window": "近 30 天",
                "items": official,
            },
            {
                "id": "discoveries",
                "title": "高价值技术发现",
                "window": "近 30 天 · 技术与证据优先",
                "items": discoveries,
            },
        ],
        "counts": {
            "projects": len(projects),
            "growth_pending": sum(p["momentum"]["signal"] is None for p in projects),
            "rising": sum(p["momentum"]["is_rising"] for p in projects),
            "new": sum(p["momentum"]["is_new"] for p in projects),
        },
        "coverage": {
            "project_candidates_truncated": project_truncated,
            "article_candidates_truncated": truncated,
            "candidate_limit": 1000,
        },
    }
