"""Durable sampling distinguishes actual observation time from configured uptime."""

from datetime import UTC, timedelta

from sqlalchemy import func, select

from .models import AnalysisAttempt, RuntimeSample, TaskRun, now


async def record_runtime_sample(db, settings):
    at = now()
    slot = at.replace(minute=at.minute // 5 * 5, second=0, microsecond=0)
    async with db.sessions() as session:
        existing = await session.get(RuntimeSample, slot)
        if existing and existing.scheduler_enabled == settings.scheduler_enabled:
            return
        active = await session.scalar(
            select(func.count())
            .select_from(TaskRun)
            .where(TaskRun.status.in_(["queued", "running"]))
        )
        if existing:
            existing.observed_at = at
            existing.scheduler_enabled = settings.scheduler_enabled
            existing.active_tasks = active
        else:
            session.add(
                RuntimeSample(
                    slot=slot,
                    observed_at=at,
                    scheduler_enabled=settings.scheduler_enabled,
                    active_tasks=active,
                )
            )
        await session.commit()


def observation_window(samples, at):
    samples = sorted(samples, key=lambda row: row.observed_at)
    enabled = [row for row in samples if row.scheduler_enabled]
    start = enabled[0].observed_at if enabled else None
    elapsed = (at - start).total_seconds() / 3600 if start else 0
    boundary = at - timedelta(hours=24)
    times = [
        row.observed_at for row in enabled if row.observed_at >= boundary - timedelta(minutes=5)
    ]
    gaps = [(b - a).total_seconds() / 60 for a, b in zip(times, times[1:], strict=False)]
    if times:
        gaps += [(at - times[-1]).total_seconds() / 60]
        if elapsed >= 24:
            gaps += [max(0, (times[0] - boundary).total_seconds() / 60)]
    complete = elapsed >= 24 and bool(times) and max(gaps, default=1440) <= 10
    return {
        "started_at": start,
        "observed_hours": round(elapsed, 2),
        "samples": len(enabled),
        "window_hours": 24,
        "max_gap_minutes": round(max(gaps, default=0), 2) if times else None,
        "status": "covered" if complete else "gaps" if elapsed >= 24 else "pending",
        "seven_day_status": "pending" if elapsed < 168 else "requires_growth_review",
    }


async def runtime_report(session, settings, at):
    samples = list(
        (
            await session.scalars(
                select(RuntimeSample)
                .where(RuntimeSample.observed_at >= at - timedelta(days=8))
                .order_by(RuntimeSample.slot)
            )
        ).all()
    )
    runs = (
        await session.execute(
            select(TaskRun.status, func.count(), func.sum(TaskRun.added), func.sum(TaskRun.failed))
            .where(TaskRun.created_at >= at - timedelta(hours=24))
            .group_by(TaskRun.status)
        )
    ).all()
    tokens = (
        await session.execute(
            select(
                func.count(),
                func.sum(AnalysisAttempt.input_tokens),
                func.sum(AnalysisAttempt.output_tokens),
            ).where(AnalysisAttempt.created_at >= at - timedelta(hours=24))
        )
    ).one()
    return {
        "observation": observation_window(samples, at),
        "scheduler_enabled": settings.scheduler_enabled,
        "concurrency": settings.collector_concurrency,
        "task_timeout_seconds": settings.task_timeout,
        "runs_24h": [
            {"status": status, "count": count, "added": added or 0, "failed": failed or 0}
            for status, count, added, failed in runs
        ],
        "llm_24h": {"attempts": tokens[0], "input_tokens": tokens[1], "output_tokens": tokens[2]},
        "collection_traffic": await collection_traffic(session, at),
    }


async def collection_traffic(session, at):
    """UTC daily body bytes from completed task observations, including failed requests."""
    at = at.astimezone(UTC)
    rows = (
        await session.execute(
            select(TaskRun.created_at, TaskRun.status, TaskRun.network_usage).where(
                TaskRun.kind == "collect", TaskRun.created_at >= at - timedelta(days=8)
            )
        )
    ).all()
    days = {
        (at - timedelta(days=offset)).date().isoformat(): {
            "requests": 0,
            "received_bytes": 0,
            "decoded_bytes": 0,
            "measured_tasks": 0,
            "unmeasured_tasks": 0,
            "running_tasks": 0,
            "unmeasured_responses": 0,
        }
        for offset in range(7)
    }
    for created_at, status, usage in rows:
        day = created_at.astimezone(UTC).date().isoformat()
        if status in {"queued", "running"}:
            if day in days:
                days[day]["running_tasks"] += 1
            continue
        if usage is None:
            if day in days:
                days[day]["unmeasured_tasks"] += 1
            continue
        entries = usage.get("days", {}) or {day: {}}
        for date, counters in entries.items():
            if date not in days:
                continue
            row = days[date]
            row["measured_tasks"] += 1
            for key in ("requests", "received_bytes", "decoded_bytes", "unmeasured_responses"):
                row[key] += counters.get(key, 0)
    return {
        "basis": "http_response_body",
        "timezone": "UTC",
        "days": [{"date": day, **counters} for day, counters in days.items()],
    }
