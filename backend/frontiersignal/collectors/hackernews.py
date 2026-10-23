import asyncio
from datetime import UTC, datetime

from ..models import now
from ..normalizer import RawItem, plain_text
from ..technical import technical_signal
from .base import Collection

BASE = "https://hacker-news.firebaseio.com/v0"


class HackerNewsCollector:
    def __init__(self, fetcher):
        self.fetcher = fetcher

    async def collect(self, source):
        result = Collection([])
        lists = await asyncio.gather(
            *(
                self.fetcher.json(f"{BASE}/{name}.json")
                for name in ["topstories", "beststories", "newstories"]
            ),
            return_exceptions=True,
        )
        ids = []
        per_list = max(1, self.fetcher.settings.hn_candidates // 3)
        for values in lists:
            if not isinstance(values, list):
                result.errors.append("HN 榜单请求失败，其他榜单继续采集")
                continue
            ids.extend(i for i in values[:per_list] if isinstance(i, int))
        semaphore = asyncio.Semaphore(4)

        async def fetch(identifier):
            async with semaphore:
                return await self.fetcher.json(f"{BASE}/item/{identifier}.json")

        payloads = await asyncio.gather(
            *(fetch(i) for i in dict.fromkeys(ids)), return_exceptions=True
        )
        articles = []
        for item in payloads:
            if isinstance(item, Exception):
                result.errors.append(f"HN 帖子请求失败（{type(item).__name__}）")
                continue
            if (
                not isinstance(item, dict)
                or item.get("deleted")
                or item.get("dead")
                or item.get("type", "story") != "story"
            ):
                continue
            signal = technical_signal(
                item.get("title"), plain_text(item.get("text", "")), "hackernews"
            )
            articles.append((signal.score, item))
        articles.sort(key=lambda pair: (pair[0], pair[1].get("score", 0)), reverse=True)
        sampled = 0
        for score, item in articles:
            comments = []
            comment_errors = 0
            if score >= 45 and sampled < 5:
                sampled += 1
                responses = await asyncio.gather(
                    *(
                        fetch(i)
                        for i in item.get("kids", [])[: self.fetcher.settings.hn_comment_limit]
                    ),
                    return_exceptions=True,
                )
                for comment in responses:
                    if isinstance(comment, Exception):
                        comment_errors += 1
                    elif (
                        isinstance(comment, dict)
                        and not comment.get("deleted")
                        and not comment.get("dead")
                    ):
                        comments.append(
                            {
                                "id": comment.get("id"),
                                "author": comment.get("by"),
                                "text": plain_text(comment.get("text", ""))[:6000],
                                "time": comment.get("time"),
                            }
                        )
                if comment_errors:
                    result.errors.append(f"HN 帖子 {item['id']} 的 {comment_errors} 条评论请求失败")
            discussion = f"https://news.ycombinator.com/item?id={item['id']}"
            metrics = {
                "kind": "discussion",
                "points": item.get("score"),
                "comments_count": item.get("descendants"),
                "discussion_url": discussion,
                "comments_sample": comments,
                "sample_limit": self.fetcher.settings.hn_comment_limit,
                "observed_at": now().isoformat(),
            }
            result.items.append(
                RawItem(
                    platform_id=str(item["id"]),
                    title=item.get("title"),
                    body=item.get("text", ""),
                    author=item.get("by"),
                    url=item.get("url") or discussion,
                    identity_url=discussion,
                    published_at=datetime.fromtimestamp(item["time"], UTC)
                    if item.get("time")
                    else None,
                    raw={**item, "comment_sample": comments},
                    metrics=metrics,
                )
            )
        result.cursor = {"last_ids": [item.platform_id for item in result.items]}
        return result
