import json
import re
from datetime import datetime

from ..normalizer import RawItem
from .base import Collection


class GitHubCollector:
    def __init__(self, fetcher):
        self.fetcher = fetcher

    async def collect(self, source):
        repo = source.config.get("repository", "")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) or any(
            part in {".", ".."} for part in repo.split("/")
        ):
            raise ValueError("GitHub repository must be owner/name")
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        token = self.fetcher.settings.github_token.get_secret_value()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if source.cursor.get("etag"):
            headers["If-None-Match"] = source.cursor["etag"]
        body, response_headers, status = await self.fetcher.get(
            f"https://api.github.com/repos/{repo}/releases?per_page={self.fetcher.settings.max_items}",
            headers,
        )
        if status == 304:
            return Collection([], source.cursor)
        items = []
        for release in json.loads(body):
            published = release.get("published_at")
            items.append(
                RawItem(
                    platform_id=str(release["id"]),
                    title=f"{repo}: {release.get('name') or release['tag_name']}",
                    body=release.get("body") or "",
                    url=release["html_url"],
                    author=(release.get("author") or {}).get("login"),
                    published_at=datetime.fromisoformat(published.replace("Z", "+00:00"))
                    if published
                    else None,
                    raw=release,
                    metrics={"kind": "release", "repository": repo},
                )
            )
        lowered = {k.lower(): v for k, v in response_headers.items()}
        return Collection(items, {"etag": lowered.get("etag")})
