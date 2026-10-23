from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from frontiersignal.collectors.github_discovery import GitHubDiscoveryCollector, discovery_search
from frontiersignal.config import Settings
from frontiersignal.models import Repository, Source, StarSnapshot, now
from frontiersignal.momentum import official_signal, project_momentum
from frontiersignal.network import FetchError
from frontiersignal.normalizer import RawItem
from frontiersignal.projects import normalize_star_history, tracking_targets
from frontiersignal.storage import ingest
from sqlalchemy import func, select

AT = datetime(2026, 10, 22, 12, tzinfo=UTC)


def repository(stars, age=5, history=None):
    return SimpleNamespace(
        stars=stars,
        created_at=AT - timedelta(days=age),
        first_seen_at=AT,
        star_history=history,
        has_code=True,
        license="MIT",
    )


def article():
    return SimpleNamespace(technical_score=90, technical_topics=["llm"], is_read=False)


def snapshots(*rows):
    return [
        SimpleNamespace(observed_at=AT - timedelta(hours=hours), stars=count)
        for hours, count in rows
    ]


def history(today, previous=24):
    return {
        "observed_at": AT.isoformat(),
        "days": [
            {
                "date": (AT - timedelta(days=index)).date().isoformat(),
                "stars": today if index == 0 else previous,
            }
            for index in range(7)
        ],
    }


def test_fast_small_project_beats_large_established_project():
    fast = project_momentum(repository(200), article(), snapshots((0, 200), (24, 100)), AT, ["llm"])
    old = project_momentum(
        repository(100010, 1000), article(), snapshots((0, 100010), (24, 100000)), AT, ["llm"]
    )
    assert fast["is_rising"] and fast["score"] > old["score"]
    assert not old["is_rising"] and not old["is_new"]
    assert fast["signal"]["relative_percent"] == 100


def test_old_repository_can_return_only_with_real_acceleration():
    result = project_momentum(
        repository(100300, 1000),
        article(),
        snapshots((0, 100300), (24, 100100), (48, 100080)),
        AT,
        [],
    )
    assert result["status"] == "surging" and result["acceleration"] == 10


def test_latest_slowdown_overrides_older_daily_hype():
    result = project_momentum(
        repository(200, 1000, history(150)), article(), snapshots((0, 200), (1, 203)), AT, []
    )
    assert result["signal"]["value"] == -3
    assert not result["is_rising"]


def test_short_window_is_not_extrapolated_into_day_growth():
    result = project_momentum(repository(125), article(), snapshots((0, 125), (1.5, 100)), AT, [])
    assert result["signal"]["value"] == 25
    assert result["signal"]["window_hours"] == 1.5
    assert result["signal"]["rate_per_hour"] == pytest.approx(25 / 1.5)


@pytest.mark.parametrize("age", [1000, -1])
def test_first_discovery_does_not_make_old_or_future_repository_new(age):
    result = project_momentum(repository(50000, age), article(), [], AT, [])
    assert not result["is_rising"] and not result["is_new"]
    assert result["signal"] is None


def test_official_current_day_is_explicit_partial_utc_window():
    result = project_momentum(repository(300, 90, history(120)), article(), [], AT, [])
    signal = result["signal"]
    assert signal["kind"] == "github_daily" and signal["value"] == 120
    assert signal["window_hours"] == 12 and signal["rate_per_hour"] == 10
    assert signal["baseline_stars"] is None
    assert signal["relative_label"] == "占当前 Stars" and signal["relative_percent"] == 40
    assert result["acceleration"] == 10 and result["status"] == "surging"


def test_zero_history_is_known_zero_but_missing_day_is_unknown():
    assert official_signal(history(0), AT)["value"] == 0
    missing = history(0)
    missing["days"] = missing["days"][1:]
    assert official_signal(missing, AT) is None


@pytest.mark.parametrize("shift", [-7, 1])
def test_stale_and_future_official_data_are_not_live_growth(shift):
    value = history(120)
    value["observed_at"] = (AT + timedelta(hours=shift)).isoformat()
    assert official_signal(value, AT) is None


def test_daily_history_normalization_keeps_utc_dates_and_does_not_fill_missing():
    sunday = datetime(2026, 10, 18, tzinfo=UTC)
    value = normalize_star_history(
        [{"week": int(sunday.timestamp()), "days": [1, 2, 3, 4, 5, 0, 0], "total": 15}], AT
    )
    assert value["days"] == [{"date": f"2026-10-{18 + i}", "stars": i + 1} for i in range(5)]
    with pytest.raises(ValueError):
        normalize_star_history(
            [{"week": int(sunday.timestamp()), "days": [1] * 7, "total": 99}], AT
        )


def test_search_rotation_covers_age_lanes_and_pages_without_unbounded_star_leaderboard():
    searches = [discovery_search(tick, AT, 10) for tick in range(64)]
    assert len({lane for _, lane in searches}) == 4
    assert {query["page"] for query, _ in searches} == {1, 2}
    for query, lane in searches:
        assert "fork:false" in query["q"] and "archived:false" in query["q"]
        assert "stars:" in query["q"]
        if lane in {"近7天新项目", "近30天新项目"}:
            assert "stars:>=5" in query["q"]
        else:
            assert "stars:20.." in query["q"]
        if query["sort"] == "stars":
            assert "created:>=2026-10-15" in query["q"]
        if lane != "中小项目新动向":
            assert "created:" in query["q"]


async def test_optional_history_failure_keeps_repository_observation():
    class Fetcher:
        settings = Settings(
            github_queries_per_run=1, github_code_checks=0, github_history_checks=1, _env_file=None
        )

        async def json(self, url, headers):
            repo = {
                "id": 1,
                "full_name": "fixture/llm",
                "html_url": "https://github.com/fixture/llm",
                "stargazers_count": 25,
                "description": "LLM inference benchmark",
                "created_at": AT.isoformat(),
            }
            if "/search/" in url:
                return {"items": [repo]}
            if "/stargazers/history" in url:
                raise FetchError("Do not reveal response content", 404)
            if "/releases" in url:
                return []
            return repo

    result = await GitHubDiscoveryCollector(Fetcher()).collect(Source(cursor={}))
    assert (
        len(result.items) == 1
        and result.items[0].repository["repository"]["stargazers_count"] == 25
    )
    assert result.errors and "star_history" not in result.items[0].repository
    assert "Do not reveal" not in str(result.errors)


async def test_tracking_reserves_slots_for_young_repositories_without_losing_old_ones(database):
    db, _ = database
    at = now()
    async with db.sessions() as session:
        source = Source(
            id="discovery",
            name="Discovery",
            kind="github_discovery",
            url="https://api.github.com/search/repositories",
        )
        session.add(source)
        await session.flush()
        for index in range(6):
            payload = {
                "id": index,
                "full_name": f"fixture/llm-{index}",
                "html_url": f"https://github.com/fixture/llm-{index}",
                "stargazers_count": 50,
                "created_at": (at - timedelta(days=2 if index >= 4 else 1000)).isoformat(),
            }
            await ingest(
                session,
                source,
                RawItem(
                    platform_id=f"repository:{index}",
                    title=f"LLM inference benchmark {index}",
                    url=payload["html_url"],
                    repository={"repository": payload, "observed_at": at.isoformat()},
                ),
            )
        await session.commit()
        targets = await tracking_targets(session, 3)
        assert {"4", "5"} <= {target["id"] for target in targets}
        assert len(targets) == 3
        assert await session.get(Repository, targets[-1]["id"])


async def test_official_history_persists_separately_without_fabricated_snapshots_or_reanalysis(
    database,
):
    db, _ = database
    async with db.sessions() as session:
        source = Source(
            id="discovery",
            name="Discovery",
            kind="github_discovery",
            url="https://api.github.com/search/repositories",
        )
        session.add(source)
        await session.flush()
        payload = {
            "id": 42,
            "full_name": "fixture/llm",
            "html_url": "https://github.com/fixture/llm",
            "stargazers_count": 100,
        }
        item = RawItem(
            platform_id="repository:42",
            title="LLM inference benchmark",
            url=payload["html_url"],
            repository={
                "repository": payload,
                "observed_at": AT.isoformat(),
                "star_history": history(20),
            },
        )
        row, _ = await ingest(session, source, item)
        row.status, row.analysis_hash = "analyzed", "existing-analysis"
        await session.commit()
        item.repository["star_history"] = history(25)
        repeated, outcome = await ingest(session, source, item)
        await session.commit()
        assert outcome == "duplicates" and repeated.analysis_hash == "existing-analysis"
        assert (await session.get(Repository, "42")).star_history["days"][0]["stars"] == 25
        assert await session.scalar(select(func.count()).select_from(StarSnapshot)) == 1
