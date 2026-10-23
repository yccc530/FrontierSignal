"""Evidence-based short-term momentum; lifetime popularity is never a ranking bonus."""

import math
from datetime import UTC, timedelta

from .projects import parse_time, snapshot_growth


def official_signal(history, at):
    if not history:
        return None
    observed = parse_time(history.get("observed_at"))
    if observed is None or not timedelta(0) <= at - observed <= timedelta(hours=6):
        return None
    days = {row["date"]: row["stars"] for row in history.get("days", [])}
    midnight = observed.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed = (observed - midnight).total_seconds() / 3600
    # A partial UTC day needs at least three hours before it can supply a velocity.
    start = midnight if elapsed >= 3 else midnight - timedelta(days=1)
    end = observed if elapsed >= 3 else midnight
    count = days.get(start.date().isoformat())
    if count is None:
        return None
    prior = [
        days.get((start - timedelta(days=offset)).date().isoformat()) for offset in range(1, 7)
    ]
    previous_rate = sum(prior) / 144 if all(value is not None for value in prior) else None
    hours = (end - start).total_seconds() / 3600
    return {
        "value": count,
        "kind": "github_daily",
        "label": "今日获星 (UTC)" if elapsed >= 3 else "昨日获星 (UTC)",
        "start_at": start,
        "end_at": end,
        "observed_at": observed,
        "window_hours": round(hours, 2),
        "rate_per_hour": count / hours,
        "previous_rate": previous_rate,
        "baseline_stars": None,
    }


def project_momentum(repository, article, snapshots, at, interests):
    age = (at - repository.created_at).total_seconds() / 86400 if repository.created_at else None
    new = age is not None and 0 <= age <= 30
    signal = None
    for hours in (1, 6, 24):
        growth = snapshot_growth(snapshots, at, hours)
        if growth["value"] is None:
            continue
        previous = snapshot_growth(snapshots, growth["baseline_at"], hours)
        signal = {
            "value": growth["value"],
            "kind": "snapshot_net",
            "label": f"约 {hours}h 净增",
            "start_at": growth["baseline_at"],
            "end_at": growth["observed_at"],
            "observed_at": growth["observed_at"],
            "window_hours": growth["window_hours"],
            "rate_per_hour": growth["value"] / growth["window_hours"],
            "previous_rate": (
                previous["value"] / previous["window_hours"]
                if previous["value"] is not None
                else None
            ),
            "baseline_stars": growth["baseline_stars"],
        }
        break
    if signal is None:
        signal = official_signal(repository.star_history, at)

    age_score = 10 * 2 ** (-max(age, 0) / 30) if age is not None and age >= 0 else 0
    quality = article.technical_score * 0.05
    quality += 3 if repository.has_code else 0
    quality += 2 if repository.license and repository.license != "NOASSERTION" else 0
    match = bool(set(article.technical_topics) & set(interests))
    score = age_score + quality + (5 if match else 0)
    reasons = []
    acceleration, share, rate = None, None, None
    rising = False
    if signal:
        value, rate = signal["value"], signal["rate_per_hour"]
        previous = signal["previous_rate"]
        acceleration = (
            rate / previous if previous is not None and previous > 0 and rate >= 0 else None
        )
        # The denominator floor limits one-star noise; it is a scoring input, not a fake baseline.
        base = signal["baseline_stars"] if signal["kind"] == "snapshot_net" else repository.stars
        share = max(0, value) / max(50, base)
        rising = (
            value >= max(5, signal["window_hours"])
            and rate >= 1
            and (share >= 0.08 or (acceleration is not None and acceleration >= 2))
        )
        score += min(30, math.log1p(max(0, rate)) / math.log(51) * 30)
        score += min(25, math.log1p(share * 100) / math.log(101) * 25)
        score += (
            min(20, max(0, math.log2(acceleration)) * 7) if acceleration and acceleration > 1 else 0
        )
        reasons.append(f"{signal['label']} {value:+d}，实际窗口 {signal['window_hours']:g} 小时")
        reasons.append(f"窗口平均 {rate:.2f} Stars/小时")
        if acceleration is not None:
            basis = "前一窗口" if signal["kind"] == "snapshot_net" else "此前6个完整UTC日平均"
            reasons.append(f"速度为{basis}的 {acceleration:.2f} 倍")
        if signal["kind"] == "github_daily":
            reasons.append("GitHub 官方逐日获星记录；UTC 日窗口，非本地快照净增")
        if base > 0:
            signal["relative_percent"] = round(value / base * 100, 2)
            signal["relative_label"] = (
                "基期增幅" if signal["kind"] == "snapshot_net" else "占当前 Stars"
            )
        else:
            signal["relative_percent"] = None
            signal["relative_label"] = "基期增幅"
    else:
        reasons.append("暂无有效短期增长证据，不以累计 Stars 或首次收录时间代替")
    if new:
        reasons.append(f"仓库实际创建于 {max(0, age):.1f} 天前")
    status = (
        "surging"
        if rising and acceleration is not None and acceleration >= 2
        else "rising"
        if rising
        else "new"
        if new
        else "watching"
    )
    score -= 5 if article.is_read else 0
    return {
        "status": status,
        "is_rising": rising,
        "is_new": new,
        "age_days": round(age, 1) if age is not None else None,
        "signal": signal,
        "acceleration": round(acceleration, 2) if acceleration is not None else None,
        "score": round(max(0, min(100, score)), 2),
        "reasons": reasons,
    }
