"""Observed repository state and timestamped, bounded star comparisons."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from .models import Article, Repository, StarSnapshot


def parse_time(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    parsed = (
        value
        if isinstance(value, datetime)
        else datetime.fromisoformat(value.replace("Z", "+00:00"))
    )
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


async def tracking_targets(session, limit: int) -> list[dict]:
    at = datetime.now(UTC)
    rows = (
        await session.scalars(
            select(Repository)
            .join(Article, Article.id == Repository.article_id)
            .where(
                Repository.tracked.is_(True),
                Repository.archived.is_(False),
                Article.status != "filtered",
            )
            .order_by(
                Repository.last_tracked_at.asc().nulls_first(),
                Repository.observed_at,
                Repository.id,
            )
            .limit(1000)
        )
    ).all()

    def active(row):
        if row.created_at and at - timedelta(days=90) <= row.created_at <= at:
            return True
        history = row.star_history or {}
        return (
            sum(
                day["stars"]
                for day in history.get("days", [])
                if (at - timedelta(days=2)).date().isoformat()
                <= day["date"]
                <= at.date().isoformat()
            )
            >= 50
        )

    # Reserve most sampling slots for young/active projects, with an overdue lane for old ones.
    focus = [row for row in rows if active(row)]
    chosen = focus[: max(1, limit * 7 // 10)]
    chosen_ids = {row.id for row in chosen}
    chosen += [row for row in rows if row.id not in chosen_ids][: limit - len(chosen)]
    return [{"id": row.id, "full_name": row.full_name} for row in chosen]


async def store_repository(session, article: Article, observation: dict):
    payload = observation["repository"]
    observed = parse_time(observation["observed_at"])
    if observed is None:
        raise ValueError("Repository observation needs its actual observation time")
    identifier = str(payload["id"])
    repository = await session.get(Repository, identifier)
    if repository and repository.observed_at > observed:
        return
    if repository is None:
        repository = Repository(id=identifier, article_id=article.id, first_seen_at=observed)
        session.add(repository)
    repository.full_name, repository.url = payload["full_name"], payload["html_url"]
    repository.description = payload.get("description")
    repository.language = payload.get("language")
    repository.license = (payload.get("license") or {}).get("spdx_id")
    repository.topics = payload.get("topics") or []
    repository.stars = int(payload["stargazers_count"])
    repository.forks = int(payload.get("forks_count", 0))
    repository.size_kb = int(payload.get("size", 0))
    repository.archived = bool(payload.get("archived"))
    repository.tracked = (
        article.technical_eligible and not repository.archived and not payload.get("fork", False)
    )
    for field in ("created_at", "pushed_at", "updated_at"):
        setattr(repository, field, parse_time(payload.get(field)))
    repository.observed_at = observed
    if observation.get("tracking_attempted"):
        repository.last_tracked_at = observed
    if "has_code" in observation:
        repository.has_code = observation["has_code"]
        repository.code_evidence = observation.get("code_evidence", [])
    if "latest_release" in observation:
        repository.latest_release = observation["latest_release"]
    if "star_history" in observation:
        repository.star_history = observation["star_history"]
    await session.flush()
    bucket = observed.replace(minute=0, second=0, microsecond=0)
    snapshot = await session.scalar(
        select(StarSnapshot).where(
            StarSnapshot.repository_id == identifier, StarSnapshot.hour_bucket == bucket
        )
    )
    if snapshot is None:
        snapshot = StarSnapshot(repository_id=identifier, hour_bucket=bucket)
        session.add(snapshot)
    snapshot.observed_at, snapshot.stars, snapshot.forks = (
        observed,
        repository.stars,
        repository.forks,
    )


def star_growth(snapshots: list, at: datetime, days: int) -> dict:
    return snapshot_growth(snapshots, at, days * 24)


def snapshot_growth(snapshots: list, at: datetime, hours: int) -> dict:
    empty = {
        "value": None,
        "baseline_at": None,
        "observed_at": None,
        "window_hours": None,
        "reason": "历史快照不足",
        "baseline_stars": None,
    }
    valid = sorted(
        (row for row in snapshots if row.observed_at <= at), key=lambda row: row.observed_at
    )
    if not valid:
        return empty
    latest = valid[-1]
    if at - latest.observed_at > timedelta(hours=6):
        return {
            **empty,
            "observed_at": latest.observed_at,
            "reason": "最新快照已超过 6 小时，等待刷新",
        }
    target = latest.observed_at - timedelta(hours=hours)
    tolerance = timedelta(hours={1: 1, 6: 2, 24: 6, 168: 12}[hours])
    baseline = next(
        (row for row in reversed(valid) if target - tolerance <= row.observed_at <= target), None
    )
    if baseline is None:
        return {**empty, "observed_at": latest.observed_at}
    return {
        "value": latest.stars - baseline.stars,
        "baseline_stars": baseline.stars,
        "baseline_at": baseline.observed_at,
        "observed_at": latest.observed_at,
        "window_hours": round(
            (latest.observed_at - baseline.observed_at).total_seconds() / 3600, 2
        ),
        "reason": "实际快照间的 Stars 净变化，包含取消 Star 的影响",
    }


def normalize_star_history(payload: list, observed: datetime) -> dict:
    observed = observed.astimezone(UTC)
    if not isinstance(payload, list) or len(payload) > 5000:
        raise ValueError("Invalid GitHub star history")
    days = {}
    for week in payload:
        if not isinstance(week, dict):
            raise ValueError("Invalid GitHub star history week")
        values, timestamp, total = week.get("days"), week.get("week"), week.get("total")
        if (
            not isinstance(values, list)
            or len(values) != 7
            or any(type(value) is not int or value < 0 for value in values)
            or type(timestamp) is not int
            or type(total) is not int
            or total != sum(values)
        ):
            raise ValueError("Invalid GitHub star history counts")
        start = datetime.fromtimestamp(timestamp, UTC)
        if start != start.replace(hour=0, minute=0, second=0, microsecond=0):
            raise ValueError("GitHub star history requires UTC day boundaries")
        for index, value in enumerate(values):
            date = (start + timedelta(days=index)).date()
            if not observed.date() - timedelta(days=15) <= date <= observed.date():
                continue
            key = date.isoformat()
            if key in days and days[key] != value:
                raise ValueError("Conflicting GitHub daily star counts")
            days[key] = value
    return {
        "observed_at": observed.isoformat(),
        "days": [{"date": date, "stars": stars} for date, stars in sorted(days.items())],
    }
