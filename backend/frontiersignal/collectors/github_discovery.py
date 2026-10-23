import re
from datetime import timedelta
from html import escape
from urllib.parse import urlencode, urlsplit

from ..models import now
from ..network import FetchError
from ..normalizer import RawItem
from ..projects import normalize_star_history, parse_time
from .base import Collection

QUERIES = [
    "topic:llm",
    '"AI agent" in:name,description',
    "topic:inference",
    "topic:fine-tuning",
    "topic:rag",
    "topic:multimodal",
    "topic:machine-learning",
    "topic:ai-framework",
]
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


def discovery_search(tick, at, per_page):
    topic = QUERIES[tick % len(QUERIES)]
    lane = (tick + tick // len(QUERIES)) % 4

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
        "page": 1 + tick // (len(QUERIES) * 4) % 3,
    }, lane_name


def github_headers(settings):
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if settings.github_token.get_secret_value():
        headers["Authorization"] = f"Bearer {settings.github_token.get_secret_value()}"
    return headers


def error_message(exc, stage):
    if isinstance(exc, FetchError) and exc.status in {403, 429}:
        return f"GitHub {stage}达到访问限制或缺少权限；可配置只读 Token 或等待额度恢复"
    return f"GitHub {stage}失败（{type(exc).__name__}）；其他已获取项目仍会保存"


class GitHubDiscoveryCollector:
    def __init__(self, fetcher):
        self.fetcher = fetcher
        self.targets: list[dict] = []

    async def collect(self, source):
        config = self.fetcher.settings
        headers = github_headers(config)
        cursor = source.cursor or {}
        tick = int(cursor.get("discovery_tick", 0)) if cursor.get("strategy") == 2 else 0
        result = Collection([], advance_on_partial=True)
        observations = {}
        for step in range(config.github_queries_per_run):
            params, lane = discovery_search(tick + step, now(), config.github_candidates_per_query)
            try:
                payload = await self.fetcher.json(
                    "https://api.github.com/search/repositories?" + urlencode(params), headers
                )
                if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                    raise ValueError("Invalid GitHub repository search response")
                if payload.get("incomplete_results"):
                    result.errors.append("GitHub 搜索返回不完整结果，未宣称覆盖全部项目")
                for repo in payload["items"]:
                    self._remember(observations, repo)
                    observations[str(repo["id"])].setdefault("discovery_queries", []).append(
                        params["q"]
                    )
                    observations[str(repo["id"])].setdefault("discovery_lanes", []).append(lane)
            except Exception as exc:
                result.errors.append(error_message(exc, "项目搜索"))
        targets = list(self.targets)
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
                repo = await self.fetcher.json(f"https://api.github.com/repos/{name}", headers)
                self._remember(observations, repo)
                item = observations[str(repo["id"])]
                item["tracking_attempted"] = True
                releases = await self.fetcher.json(
                    f"https://api.github.com/repos/{name}/releases?per_page=3", headers
                )
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
                            },
                        )
                    )
            except Exception as exc:
                result.errors.append(error_message(exc, f"版本跟踪 {name}"))
        recent = sorted(
            observations.values(),
            key=lambda item: item["repository"].get("created_at") or "",
            reverse=True,
        )
        tracked = [observations[str(t["id"])] for t in targets if str(t["id"]) in observations]
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
        repository_items = []
        for observation in observations.values():
            repo = observation["repository"]
            text = "\n".join(
                filter(
                    None,
                    [
                        repo.get("description"),
                        "Topics: " + ", ".join(repo.get("topics") or []),
                        "Language: " + (repo.get("language") or "unknown"),
                    ],
                )
            )
            repository_items.append(
                RawItem(
                    platform_id=f"repository:{repo['id']}",
                    title=repo["full_name"],
                    body=escape(text),
                    url=repo["html_url"],
                    author=(repo.get("owner") or {}).get("login"),
                    published_at=parse_time(repo.get("created_at")),
                    raw=observation,
                    metrics={
                        "kind": "repository",
                        "stars": repo["stargazers_count"],
                        "forks": repo.get("forks_count", 0),
                        "topics": repo.get("topics", []),
                        "language": repo.get("language"),
                        "archived": repo.get("archived", False),
                        "fork": repo.get("fork", False),
                        "observed_at": observation["observed_at"],
                        "pushed_at": repo.get("pushed_at"),
                    },
                    repository=observation,
                )
            )
        result.items = repository_items + result.items
        result.cursor = {
            "strategy": 2,
            "discovery_tick": tick + config.github_queries_per_run,
        }
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
        }
