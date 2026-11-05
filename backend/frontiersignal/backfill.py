"""Finite official API queries. A finished page is never full-window coverage."""

import asyncio
import json
from datetime import UTC, date, timedelta
from typing import Literal
from urllib.parse import urlencode, urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .collectors.base import Collection
from .collectors.github_discovery import (
    GitHubDiscoveryCollector,
    error_message,
    github_headers,
    repository_item,
)
from .collectors.rss import parse_entries
from .models import now
from .network import FetchError
from .projects import parse_time
from .topics import CATALOG, selected_topics

ARXIV_CATEGORIES = {"cs.AI", "cs.LG", "cs.CL", "cs.CV"}


class BackfillRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_date: date
    end_date: date
    max_pages: int = Field(2, ge=1, le=5)
    start_page: int = Field(1, ge=1, le=5)
    per_page: int = Field(20, ge=1, le=50)
    topics: list[str] | None = Field(None, min_length=1, max_length=2)
    github_date_field: Literal["created", "pushed", "both"] = "both"

    @model_validator(mode="after")
    def finite_window(self):
        today = now().date()
        if not today - timedelta(days=90) <= self.start_date <= self.end_date <= today:
            raise ValueError("补采日期须在最近 90 天内，开始日期不得晚于结束日期或今天（UTC）")
        if (self.end_date - self.start_date).days >= 31:
            raise ValueError("每次最多补采 31 个 UTC 日期")
        if self.start_page + self.max_pages - 1 > 5:
            raise ValueError("起始页与页数不能超出第5页的有界范围")
        if self.topics is not None and (
            len(set(self.topics)) != len(self.topics)
            or any(key not in CATALOG for key in self.topics)
        ):
            raise ValueError("补采主题须来自既有主题目录，不能重复")
        return self


def backfill_groups(source, request: BackfillRequest):
    if source.kind == "github_discovery":
        keys = request.topics or selected_topics(source)[:2]
        if any(not CATALOG[key].github_query for key in keys):
            raise ValueError("所选方向没有已接入的 GitHub 查询")
        return [(key, CATALOG[key].label, CATALOG[key].github_query) for key in keys]
    if source.kind == "arxiv":
        if (source.config or {}).get("research_queries"):
            keys = request.topics or selected_topics(source)[:2]
            if any(not CATALOG[key].arxiv_query for key in keys):
                raise ValueError("所选方向没有已接入的 arXiv 专项查询")
            return [(key, CATALOG[key].label, CATALOG[key].arxiv_query) for key in keys]
        parsed = urlsplit(source.url)
        category = parsed.path.removeprefix("/rss/")
        if parsed.hostname == "rss.arxiv.org" and category in ARXIV_CATEGORIES:
            if request.topics:
                raise ValueError("分类订阅补采使用原有分类，不接受专项主题")
            return [(category, category, f"cat:{category}")]
    raise ValueError("该来源仅提供当前窗口，不支持历史回补；不会把当前 RSS 当成历史数据")


def backfill_plan(source, request):
    groups = backfill_groups(source, request)
    fields = (
        (
            ["created", "pushed"]
            if request.github_date_field == "both"
            else [request.github_date_field]
        )
        if source.kind == "github_discovery"
        else ["submittedDate"]
    )
    return {
        "bounded": True,
        "timezone": "UTC",
        "start_date": request.start_date.isoformat(),
        "end_date": request.end_date.isoformat(),
        "groups": [{"id": key, "label": label} for key, label, _ in groups],
        "date_fields": fields,
        "max_requests": len(groups) * len(fields) * request.max_pages,
        "max_candidates": len(groups) * len(fields) * request.max_pages * request.per_page,
        "max_pages": request.max_pages,
        "start_page": request.start_page,
        "end_page": request.start_page + request.max_pages - 1,
        "per_page": request.per_page,
        "automatic_analysis": False,
        "coverage": "bounded; never proves the whole date window is covered",
    }


def in_window(value, request):
    try:
        value = parse_time(value)
        return (
            value is not None
            and request.start_date <= value.astimezone(UTC).date() <= request.end_date
        )
    except (TypeError, ValueError, AttributeError):
        return False


async def backfill_pages(fetcher, source, request):
    """Yield each page before requesting another, so earlier originals survive failure."""
    plan = backfill_plan(source, request)
    for key, label, query in backfill_groups(source, request):
        for field in plan["date_fields"]:
            seen_pages = set()
            for page in range(request.start_page, request.start_page + request.max_pages):
                record = {"group": key, "label": label, "date_field": field, "page": page}
                result = Collection([])
                try:
                    if source.kind == "arxiv":
                        params = {
                            "search_query": f"({query}) AND submittedDate:[{request.start_date:%Y%m%d}0000 TO {request.end_date:%Y%m%d}2359]",
                            "sortBy": "submittedDate",
                            "sortOrder": "descending",
                            "start": (page - 1) * request.per_page,
                            "max_results": request.per_page,
                        }
                        body, _, _ = await fetcher.get(
                            "https://export.arxiv.org/api/query?" + urlencode(params)
                        )
                        items = await asyncio.to_thread(parse_entries, body, request.per_page)
                        if any("api/errors" in (item.platform_id or "") for item in items):
                            raise ValueError("arXiv API 返回查询错误")
                        record["query"] = params["search_query"]
                        for item in items:
                            item.metrics["query_topics"] = [key] if key in CATALOG else []
                        dates = [item.published_at for item in items]
                    else:
                        params = {
                            "q": f"{query} {field}:{request.start_date}..{request.end_date} fork:false archived:false",
                            "sort": "updated" if field == "pushed" else "stars",
                            "order": "desc",
                            "per_page": request.per_page,
                            "page": page,
                        }
                        payload = await fetcher.json(
                            "https://api.github.com/search/repositories?" + urlencode(params),
                            github_headers(fetcher.settings),
                        )
                        if not isinstance(payload, dict) or not isinstance(
                            payload.get("items"), list
                        ):
                            raise ValueError("Invalid GitHub repository search response")
                        if len(payload["items"]) > request.per_page:
                            raise ValueError("GitHub 返回条数超过本次分页预算")
                        observations = {}
                        dates = []
                        for repo in payload["items"]:
                            GitHubDiscoveryCollector._remember(observations, repo)
                            dates.append(
                                repo.get("created_at" if field == "created" else "pushed_at")
                            )
                        items = [
                            repository_item(observation) for observation in observations.values()
                        ]
                        record.update(query=params["q"], reported_total=payload.get("total_count"))
                        if payload.get("incomplete_results"):
                            result.errors.append(
                                "GitHub 搜索返回 incomplete_results，窗口覆盖不完整"
                            )
                    identifiers = tuple(item.platform_id for item in items)
                    fingerprint = json.dumps(identifiers)
                    if identifiers and fingerprint in seen_pages:
                        raise ValueError("上游返回重复页，已停止该查询，未假装继续覆盖")
                    seen_pages.add(fingerprint)
                    outside = 0
                    for item, timestamp in zip(items, dates, strict=True):
                        match = in_window(timestamp, request)
                        outside += not match
                        item.defer_analysis = True
                        item.metrics["backfill"] = {
                            "start_date": request.start_date.isoformat(),
                            "end_date": request.end_date.isoformat(),
                            "timezone": "UTC",
                            "date_field": field,
                            "matches_requested_window": match,
                            "query": record["query"],
                            "page": page,
                            "observed_at": now().isoformat(),
                        }
                    if outside:
                        result.errors.append(
                            f"{outside} 条返回的日期缺失或超出请求窗口；原始内容保留，不计为窗口覆盖"
                        )
                    result.items = items
                    record.update(
                        candidates=len(items),
                        outside_window=outside,
                        status="partial" if result.errors else "bounded",
                    )
                except Exception as exc:
                    result.errors.append(
                        error_message(exc, "有界补采")
                        if source.kind == "github_discovery"
                        else f"arXiv 有界补采失败：{exc}"
                        if isinstance(exc, FetchError)
                        else f"arXiv 有界补采失败（{type(exc).__name__}）"
                    )
                    record.update(
                        candidates=0,
                        status="failed",
                        error_type=type(exc).__name__,
                        http_status=getattr(exc, "status", None),
                    )
                yield result, record
                if record["status"] == "failed" or len(result.items) < request.per_page:
                    break
