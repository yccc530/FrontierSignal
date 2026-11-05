import base64
import json
import re
from datetime import timedelta
from html import escape
from urllib.parse import urlencode, urlsplit

from ..discovery_budget import current_budget
from ..discovery_state import record_scan
from ..github_catalog import (
    FIXED_REPOSITORIES,
    ORGANIZATIONS,
    fixed_repository,
    organization_identity,
)
from ..models import now
from ..network import FetchError
from ..normalizer import RawItem
from ..projects import normalize_star_history, parse_time
from ..topics import CATALOG, collection_topics, selected_topics
from .base import Collection

QUERIES = [CATALOG[key].github_query for key in collection_topics("github_discovery")]
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
CODE_EXTENSIONS = (
    ".py",
    ".rs",
    ".go",
    ".cpp",
    ".cc",
    ".c",
    ".ts",
    ".tsx",
    ".js",
    ".ipynb",
    ".cu",
    ".java",
)


def topic_queries(topics, tick):
    cycle = tick // len(topics)
    queries = []
    for key in topics:
        variants = [CATALOG[key].github_query, *CATALOG[key].github_alternates]
        queries.append(variants[cycle % len(variants)])
    return queries


def discovery_search(tick, at, per_page, queries=None, max_pages=3):
    queries = QUERIES if queries is None else queries
    topic = queries[tick % len(queries)]
    lane = (tick + tick // len(queries)) % 4

    def date(days):
        return (at - timedelta(days=days)).date().isoformat()

    windows = [
        (f"created:>={date(7)} stars:>=5", "stars", "近7天新项目"),
        (f"created:{date(30)}..{date(8)} stars:>=5", "updated", "近30天新项目"),
        (f"created:{date(90)}..{date(31)} stars:20..20000", "updated", "近90天成长项目"),
        ("stars:20..50000", "updated", "中小项目新动向"),
    ]
    filters, sort, lane_name = windows[lane]
    return {
        "q": f"{topic} {filters} fork:false archived:false pushed:>={date(3 if lane == 3 else 14)}",
        "sort": sort,
        "order": "desc",
        "per_page": per_page,
        "page": 1 + tick // (len(queries) * 4) % max_pages,
    }, lane_name


def infrastructure_search(tick, at, per_page, queries, max_pages):
    return {
        "q": f"{queries[tick % len(queries)]} stars:>=10000 fork:false archived:false pushed:>={(at - timedelta(days=30)).date()}",
        "sort": "stars" if tick % 2 == 0 else "updated",
        "order": "desc",
        "per_page": per_page,
        "page": 1 + tick // len(queries) % max_pages,
    }


def github_headers(settings):
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if settings.github_token.get_secret_value():
        headers["Authorization"] = f"Bearer {settings.github_token.get_secret_value()}"
    return headers


def error_message(exc, stage):
    if isinstance(exc, FetchError) and exc.rate_limited:
        return f"GitHub {stage}未完成：{exc}"
    if isinstance(exc, FetchError) and exc.status in {403, 429}:
        return f"GitHub {stage}达到访问限制或缺少权限；可配置只读 Token 或等待额度恢复"
    return f"GitHub {stage}失败（{type(exc).__name__}）；其他已获取项目仍会保存"


def repository_item(observation):
    repo = observation["repository"]
    text = "\n".join(
        filter(
            None,
            [
                repo.get("description"),
                "Topics: " + ", ".join(repo.get("topics") or []),
                "Language: " + (repo.get("language") or "unknown"),
                observation.get("readme"),
            ],
        )
    )
    return RawItem(
        platform_id=f"repository:{repo['id']}",
        title=repo["full_name"],
        body=escape(text),
        url=repo["html_url"],
        author=(repo.get("owner") or {}).get("login"),
        published_at=parse_time(repo.get("created_at")),
        raw=observation,
        preserve_existing_content="readme" not in observation,
        metrics={
            "kind": "repository",
            "discovery_groups": observation.get("discovery_groups", []),
            "stars": repo["stargazers_count"],
            "forks": repo.get("forks_count", 0),
            "topics": repo.get("topics", []),
            "language": repo.get("language"),
            "archived": repo.get("archived", False),
            "fork": repo.get("fork", False),
            "observed_at": observation["observed_at"],
            "pushed_at": repo.get("pushed_at"),
            "resource": observation.get("resource", {}),
            "has_code": observation.get("has_code"),
            "discovery_channels": observation.get("discovery_channels", []),
            "infrastructure": observation.get("infrastructure"),
            "official_organization": observation.get("official_organization"),
        },
        repository=observation,
    )


class GitHubDiscoveryCollector:
    def __init__(self, fetcher):
        self.fetcher = fetcher
        self.targets: list[dict] = []
        self.known_resources: dict[str, dict] = {}
        self.http_cache = {}

    async def conditional_json(self, url, headers, *, releases=False):
        if not hasattr(self.fetcher, "get"):
            return await self.fetcher.json(url, headers)
        cached = self.http_cache.get(url, {})
        request_headers = dict(headers)
        if cached.get("etag"):
            request_headers["If-None-Match"] = cached["etag"]
        body, response_headers, status = await self.fetcher.get(url, request_headers)
        if status == 304:
            if not cached or (not releases and "payload" not in cached):
                raise ValueError("GitHub returned 304 without a saved representation")
            cached["checked_at"] = now().isoformat()
            return None if releases else cached["payload"]
        payload = json.loads(body)
        lowered = {key.lower(): value for key, value in response_headers.items()}
        entry = {"etag": lowered.get("etag"), "checked_at": now().isoformat()}
        if releases:
            if not isinstance(payload, list):
                raise ValueError("Invalid releases")
            visible = [release for release in payload if not release.get("draft")]
            entry["latest"] = (
                {
                    key: visible[0].get(key)
                    for key in ["tag_name", "name", "html_url", "published_at"]
                }
                if visible
                else None
            )
        else:
            entry["payload"] = payload
        if len(json.dumps(entry)) <= 100_000:
            self.http_cache[url] = entry
        else:
            self.http_cache.pop(url, None)
        return payload

    async def collect(self, source):
        config = self.fetcher.settings
        budget = current_budget(config)
        headers = github_headers(config)
        cursor = source.cursor or {}
        self.http_cache = dict(cursor.get("http_cache", {}))
        tick = int(cursor.get("discovery_tick", 0)) if cursor.get("strategy") == 2 else 0
        result = Collection([], advance_on_partial=True)
        observations = {}
        topics = selected_topics(source, "github_discovery")
        scans = dict(cursor.get("scans", {}))
        steps = min(
            config.github_queries_per_run
            - budget.github_mature_queries
            - budget.github_organization_queries,
            len(topics),
        )
        searches = []
        for step in range(steps):
            topic = topics[(tick + step) % len(topics)]
            params, lane = discovery_search(
                tick + step,
                now(),
                config.github_candidates_per_query,
                topic_queries(topics, tick + step),
                config.github_search_pages,
            )
            searches.append((topic, CATALOG[topic].label, [topic], params, lane, "growth"))
        mature_tick = int(cursor.get("mature_tick", 0))
        for step in range(budget.github_mature_queries):
            params = infrastructure_search(
                mature_tick + step,
                now(),
                config.github_candidates_per_query,
                topic_queries(topics, mature_tick + step),
                config.github_search_pages,
            )
            searches.append(
                (
                    "infrastructure",
                    "常用基础设施",
                    [],
                    params,
                    "累计 Stars 与近30天维护",
                    "infrastructure",
                )
            )
        organization_tick = int(cursor.get("organization_tick", 0))
        for step in range(budget.github_organization_queries):
            login, label, _ = ORGANIZATIONS[(organization_tick + step) % len(ORGANIZATIONS)]
            params = {
                "q": f"org:{login} fork:false archived:false pushed:>={(now() - timedelta(days=30)).date()}",
                "sort": "updated",
                "order": "desc",
                "per_page": config.github_candidates_per_query,
                "page": 1
                + (organization_tick + step) // len(ORGANIZATIONS) % config.github_search_pages,
            }
            searches.append(
                (
                    f"organization:{login}",
                    f"官方组织 · {label}",
                    [],
                    params,
                    "官方组织最近更新",
                    "official",
                )
            )
        for group, label, group_topics, params, lane, channel in searches:
            try:
                payload = await self.fetcher.json(
                    "https://api.github.com/search/repositories?" + urlencode(params), headers
                )
                if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                    raise ValueError("Invalid GitHub repository search response")
                if payload.get("incomplete_results"):
                    result.errors.append("GitHub 搜索返回不完整结果，未宣称覆盖全部项目")
                record_scan(
                    scans,
                    group,
                    label=label,
                    topics=group_topics,
                    count=len(payload["items"]),
                    error="GitHub 搜索结果不完整" if payload.get("incomplete_results") else None,
                    partial=True,
                    filtered=0,
                )
                scans[group]["query"] = params["q"]
                for repo in payload["items"]:
                    self._remember(observations, repo)
                    observations[str(repo["id"])].setdefault("discovery_queries", []).append(
                        params["q"]
                    )
                    observations[str(repo["id"])].setdefault("discovery_lanes", []).append(lane)
                    observation = observations[str(repo["id"])]
                    observation.setdefault("discovery_groups", []).append(group)
                    observation.setdefault("discovery_channels", []).append(channel)
                    if channel == "infrastructure":
                        observation["infrastructure"] = {
                            "kind": "mature",
                            "label": "成熟项目查询",
                            "query": params["q"],
                            "basis": "累计 Stars ≥10000 且近30天维护；不代表近期增长",
                        }
            except Exception as exc:
                error = error_message(exc, "项目搜索")
                result.errors.append(error)
                record_scan(scans, group, label=label, topics=group_topics, error=error)
        fixed_tick = int(cursor.get("fixed_tick", 0))
        fixed_targets = [
            {
                "full_name": FIXED_REPOSITORIES[(fixed_tick + step) % len(FIXED_REPOSITORIES)][0],
                "fixed": True,
            }
            for step in range(budget.github_fixed_per_run)
        ]
        targets = (
            (
                fixed_targets
                + [target for target in self.targets if not fixed_repository(target["full_name"])]
            )[: config.github_track_per_run]
            if fixed_targets
            else list(self.targets)
        )
        if not targets:
            targets = [
                {"id": identifier, "full_name": item["repository"]["full_name"]}
                for identifier, item in list(observations.items())[: config.github_track_per_run]
            ]
        for target in targets:
            name = target["full_name"]
            if not REPOSITORY.fullmatch(name) or any(
                part in {".", ".."} for part in name.split("/")
            ):
                result.errors.append("GitHub 已跟踪项目名称无效")
                continue
            try:
                repo = await self.conditional_json(f"https://api.github.com/repos/{name}", headers)
                self._remember(observations, repo)
                target["id"] = str(repo["id"])
                item = observations[str(repo["id"])]
                item["tracking_attempted"] = True
                if target.get("fixed"):
                    item["infrastructure"] = fixed_repository(name)
                    item.setdefault("discovery_channels", []).append("infrastructure")
                    item.setdefault("discovery_groups", []).append(f"fixed:{name}")
                release_url = f"https://api.github.com/repos/{name}/releases?per_page=3"
                releases = await self.conditional_json(
                    release_url,
                    headers,
                    releases=True,
                )
                if releases is None:
                    item["latest_release"] = self.http_cache[release_url].get("latest")
                    if target.get("fixed"):
                        record_scan(
                            scans,
                            f"fixed:{name}",
                            label=f"固定跟踪 · {name}",
                            topics=[],
                            count=1,
                            filtered=0,
                        )
                    continue
                if not isinstance(releases, list):
                    raise ValueError("Invalid releases")
                releases = [release for release in releases if not release.get("draft")]
                item["latest_release"] = (
                    {
                        key: releases[0].get(key)
                        for key in ["tag_name", "name", "html_url", "published_at"]
                    }
                    if releases
                    else None
                )
                for release in releases:
                    result.items.append(
                        RawItem(
                            platform_id=f"release:{release['id']}",
                            title=f"{name}: {release.get('name') or release.get('tag_name')}",
                            body=release.get("body") or "",
                            url=release["html_url"],
                            author=(release.get("author") or {}).get("login"),
                            published_at=parse_time(release.get("published_at")),
                            raw=release,
                            metrics={
                                "kind": "release",
                                "repository": name,
                                "topics": repo.get("topics", []),
                                "language": repo.get("language"),
                                "infrastructure": item.get("infrastructure"),
                                "official_organization": organization_identity(
                                    (repo.get("owner") or {}).get("login")
                                ),
                            },
                        )
                    )
                if target.get("fixed"):
                    record_scan(
                        scans,
                        f"fixed:{name}",
                        label=f"固定跟踪 · {name}",
                        topics=[],
                        count=1,
                        filtered=0,
                    )
            except Exception as exc:
                result.errors.append(error_message(exc, f"版本跟踪 {name}"))
                if target.get("fixed"):
                    record_scan(
                        scans,
                        f"fixed:{name}",
                        label=f"固定跟踪 · {name}",
                        topics=[],
                        count=int(str(target.get("id")) in observations),
                        partial=str(target.get("id")) in observations,
                        error=error_message(exc, "固定仓库跟踪"),
                    )
        recent = sorted(
            observations.values(),
            key=lambda item: item["repository"].get("created_at") or "",
            reverse=True,
        )
        tracked = [
            observations[str(t.get("id"))] for t in targets if str(t.get("id")) in observations
        ]
        history_candidates = recent[: (config.github_history_checks + 1) // 2] + tracked + recent
        checked = set()
        for observation in history_candidates:
            repo = observation["repository"]
            if len(checked) >= config.github_history_checks:
                break
            if repo["id"] in checked:
                continue
            checked.add(repo["id"])
            try:
                weeks = await self.fetcher.json(
                    f"https://api.github.com/repos/{repo['full_name']}/stargazers/history", headers
                )
                observation["star_history"] = normalize_star_history(weeks, now())
                observation["star_history_raw"] = weeks
            except Exception as exc:
                result.errors.append(error_message(exc, f"获星历史 {repo['full_name']}"))
                if isinstance(exc, FetchError) and exc.status in {403, 429}:
                    break
        for observation in list(observations.values())[: config.github_code_checks]:
            repo = observation["repository"]
            name = repo["full_name"]
            try:
                entries = await self.fetcher.json(
                    f"https://api.github.com/repos/{name}/contents", headers
                )
                if not isinstance(entries, list):
                    raise ValueError("Invalid repository contents")
                files = [
                    entry["name"]
                    for entry in entries
                    if entry.get("type") == "file"
                    and str(entry.get("name", "")).endswith(CODE_EXTENSIONS)
                ]
                directories = [
                    entry["name"]
                    for entry in entries
                    if entry.get("type") == "dir"
                    and entry.get("name") in {"src", "lib", "packages", "models", "python"}
                ]
                observation["has_code"] = True if files else None
                observation["code_evidence"] = (
                    [f"根目录含代码文件：{', '.join(files[:4])}"]
                    if files
                    else [f"待进一步核验代码目录：{', '.join(directories)}"]
                    if directories
                    else ["根目录未发现代码文件，未递归核验"]
                )
            except Exception as exc:
                result.errors.append(error_message(exc, f"代码核验 {name}"))
        readme_budget = config.github_readme_checks
        for observation in observations.values():
            repo = observation["repository"]
            previous = self.known_resources.get(repo["full_name"], {})
            resource = dict(previous)
            observation["resource"] = resource
            if previous.get("readme_sha") and previous.get("pushed_at") == repo.get("pushed_at"):
                resource["readme_status"] = "cached"
                continue
            resource["readme_status"] = "stale" if previous.get("readme_sha") else "not_fetched"
            if readme_budget <= 0:
                continue
            readme_budget -= 1
            try:
                readme = await self.fetcher.json(
                    f"https://api.github.com/repos/{repo['full_name']}/readme", headers
                )
                if readme.get("encoding") != "base64" or not re.fullmatch(
                    r"[0-9a-f]{40}", readme.get("sha", "")
                ):
                    raise ValueError("Invalid README metadata")
                content = base64.b64decode(readme["content"]).decode("utf-8", errors="replace")
                observation["readme"] = content[:24000]
                resource.update(
                    {
                        "readme_sha": readme["sha"],
                        "pushed_at": repo.get("pushed_at"),
                        "readme_status": "available",
                        "readme_truncated": len(content) > 24000,
                        "source_url": f"https://api.github.com/repos/{repo['full_name']}/git/blobs/{readme['sha']}",
                    }
                )
            except FetchError as exc:
                if exc.status != 404:
                    result.errors.append(error_message(exc, f"README {repo['full_name']}"))
                resource["readme_status"] = "unavailable"
            except Exception as exc:
                result.errors.append(error_message(exc, f"README {repo['full_name']}"))
                resource["readme_status"] = "unavailable"
        repository_items = [repository_item(observation) for observation in observations.values()]
        result.items = repository_items + result.items
        result.cursor = {
            "strategy": 2,
            "discovery_tick": tick + steps,
            "mature_tick": mature_tick + budget.github_mature_queries,
            "organization_tick": organization_tick + budget.github_organization_queries,
            "fixed_tick": fixed_tick + budget.github_fixed_per_run,
            "http_cache": {},
            "scans": {
                key: value
                for key, value in scans.items()
                if key in collection_topics("github_discovery")
                or key == "infrastructure"
                or key.startswith(("fixed:", "organization:"))
            },
        }
        cache_size = 0

        def cache_priority(row):
            parts = urlsplit(row[0]).path.split("/")
            name = "/".join(parts[2:4])
            return bool(fixed_repository(name)), row[1].get("checked_at", "")

        for url, entry in sorted(self.http_cache.items(), key=cache_priority, reverse=True):
            cache_size += len(json.dumps(entry))
            if cache_size > 2_000_000 or len(result.cursor["http_cache"]) >= 64:
                break
            result.cursor["http_cache"][url] = entry
        return result

    @staticmethod
    def _remember(observations, repo):
        if (
            not isinstance(repo, dict)
            or not isinstance(repo.get("stargazers_count"), int)
            or repo["stargazers_count"] < 0
        ):
            raise ValueError("Invalid repository metrics")
        if not REPOSITORY.fullmatch(repo.get("full_name", "")) or repo.get("private"):
            raise ValueError("Invalid public repository")
        link = urlsplit(repo.get("html_url", ""))
        if (
            link.scheme != "https"
            or link.hostname != "github.com"
            or link.username
            or link.password
        ):
            raise ValueError("Invalid public repository URL")
        identifier = str(repo["id"])
        observations[identifier] = {
            **observations.get(identifier, {}),
            "repository": repo,
            "observed_at": now().isoformat(),
            "official_organization": organization_identity((repo.get("owner") or {}).get("login")),
        }
