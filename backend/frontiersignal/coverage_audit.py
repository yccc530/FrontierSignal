"""Report collection evidence and missing activity without claiming complete recall."""

from collections import defaultdict
from datetime import UTC, timedelta

from sqlalchemy import func, select

from .backfill import BackfillRequest, backfill_plan
from .collectors.arxiv import research_groups
from .collectors.huggingface import dataset_groups, model_groups
from .discovery_state import scan_rows
from .github_catalog import FIXED_REPOSITORIES, ORGANIZATIONS
from .models import Source, TaskRun
from .projects import parse_time
from .topics import CATALOG


def query_groups(source, config):
    if source.kind == "github_discovery":
        groups = [
            {"id": key, "label": CATALOG[key].label, "topics": [key]}
            for key in source.discovery_topics
        ]
        if config and config.github_mature_queries:
            groups.append({"id": "infrastructure", "label": "常用基础设施", "topics": []})
        if config and config.github_organization_queries:
            groups.extend(
                {"id": f"organization:{login}", "label": f"官方组织 · {label}", "topics": []}
                for login, label, _ in ORGANIZATIONS
            )
        if config and config.github_fixed_per_run:
            groups.extend(
                {"id": f"fixed:{name}", "label": f"固定跟踪 · {name}", "topics": []}
                for name, _, _ in FIXED_REPOSITORIES
            )
    elif source.kind == "hf_models":
        groups = model_groups(source)
    elif source.kind == "hf_datasets":
        groups = dataset_groups(source)
    elif source.kind == "arxiv" and source.discovery_topics:
        groups = research_groups(source)
    else:
        groups = []
    known = {group["id"] for group in groups}
    groups.extend(
        {"id": key, "label": value.get("label", key), "topics": value.get("topics", [])}
        for key, value in (source.cursor or {}).get("scans", {}).items()
        if key not in known
    )
    return scan_rows(source, groups)


async def coverage_audit(session, at, config=None):
    sources = (await session.scalars(select(Source).order_by(Source.name))).all()
    boundary = at - timedelta(days=7)
    totals = (
        await session.execute(
            select(
                TaskRun.source_id,
                func.count(),
                func.sum(TaskRun.added),
                func.sum(TaskRun.updated),
                func.sum(TaskRun.duplicates),
                func.sum(TaskRun.filtered),
                func.sum(TaskRun.failed),
            )
            .where(TaskRun.created_at >= boundary, TaskRun.kind.in_(["collect", "backfill"]))
            .group_by(TaskRun.source_id)
        )
    ).all()
    total_map = {
        row[0]: dict(
            zip(
                ["tasks", "added", "updated", "duplicates", "filtered", "failed"],
                row[1:],
                strict=True,
            )
        )
        for row in totals
    }
    activity = defaultdict(set)
    dates = (
        await session.execute(
            select(TaskRun.source_id, TaskRun.finished_at)
            .where(
                TaskRun.created_at >= boundary,
                TaskRun.kind == "collect",
                TaskRun.status == "success",
            )
            .order_by(TaskRun.created_at.desc())
            .limit(10001)
        )
    ).all()
    for source_id, timestamp in dates[:10000]:
        if timestamp:
            activity[source_id].add(timestamp.astimezone(UTC).date())
    backfills = (
        await session.scalars(
            select(TaskRun)
            .where(TaskRun.kind == "backfill", TaskRun.created_at >= boundary)
            .order_by(TaskRun.created_at.desc())
            .limit(101)
        )
    ).all()
    results = []
    for source in sources:
        age = (
            (at - source.last_success_at).total_seconds() / 3600 if source.last_success_at else None
        )
        hints = []
        if source.enabled and (age is None or age > 168):
            hints.append("最近7天没有成功采集记录")
        scans = []
        for value in query_groups(source, config):
            try:
                scanned = parse_time(value.get("last_scan_at"))
            except (ValueError, TypeError):
                scanned = None
            scan_age = (at - scanned).total_seconds() / 3600 if scanned else None
            scan_hints = []
            if scan_age is None:
                scan_hints.append("尚无扫描证据")
            elif scan_age > max(24, source.interval_minutes / 30):
                scan_hints.append("该查询组长时间未扫描")
            if value.get("candidates") == 0:
                scan_hints.append("最近一轮零候选")
            if value.get("error"):
                scan_hints.append("最近查询失败或返回不完整")
            scans.append(
                {
                    **value,
                    "filtered": value.get("filtered"),
                    "hours_since_scan": round(scan_age, 1) if scan_age is not None else None,
                    "gaps": scan_hints,
                }
            )
        try:
            plan = backfill_plan(source, BackfillRequest(start_date=at.date(), end_date=at.date()))
            capability = {
                "supported": True,
                "kind": "official-api-bounded",
                "groups": plan["groups"],
                "full_window_recovery": False,
            }
        except ValueError:
            capability = {
                "supported": False,
                "kind": "current-window-only",
                "full_window_recovery": False,
            }
            if source.kind in {"rss", "arxiv"}:
                hints.append("当前 RSS 窗口不可用于历史回补")
        missing_days = [
            (at.astimezone(UTC).date() - timedelta(days=offset)).isoformat()
            for offset in range(6, -1, -1)
            if at.astimezone(UTC).date() - timedelta(days=offset) not in activity[source.id]
        ]
        results.append(
            {
                "source_id": source.id,
                "name": source.name,
                "kind": source.kind,
                "enabled": source.enabled,
                "last_success_at": source.last_success_at,
                "hours_since_success": round(age, 1) if age is not None else None,
                "last_status": source.last_status,
                "last_error": source.last_error,
                "totals_7d": total_map.get(
                    source.id,
                    {
                        key: 0
                        for key in ["tasks", "added", "updated", "duplicates", "filtered", "failed"]
                    },
                ),
                "days_without_successful_collection": missing_days if len(dates) <= 10000 else None,
                "groups": scans,
                "backfill": capability,
                "gaps": hints,
            }
        )
    return {
        "observed_at": at,
        "timezone": "UTC",
        "window_start": boundary,
        "sources": results,
        "backfills": [
            {
                "id": run.id,
                "source_id": run.source_id,
                "status": run.status,
                "created_at": run.created_at,
                "details": run.details,
                "added": run.added,
                "duplicates": run.duplicates,
                "filtered": run.filtered,
                "failed": run.failed,
            }
            for run in backfills[:100]
        ],
        "activity_truncated": len(dates) > 10000,
        "backfills_truncated": len(backfills) > 100,
        "coverage_basis": "无成功采集记录的 UTC 日期表示活动缺口；成功查询和有界补采均不证明该日期内容已全量覆盖",
    }
