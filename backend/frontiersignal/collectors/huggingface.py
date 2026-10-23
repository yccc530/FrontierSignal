from html import escape
from urllib.parse import quote, urlencode

from ..models import now
from ..normalizer import RawItem
from ..projects import parse_time
from .base import Collection


class HuggingFaceCollector:
    def __init__(self, fetcher):
        self.fetcher = fetcher

    async def collect(self, source):
        family = "models" if source.kind == "hf_models" else "datasets"
        params = {
            "sort": "trendingScore",
            "limit": min(20, self.fetcher.settings.max_items),
            "full": "true",
        }
        payload = await self.fetcher.json(
            f"https://huggingface.co/api/{family}?{urlencode(params)}"
        )
        if not isinstance(payload, list):
            raise ValueError("Hugging Face 返回的资源列表格式异常")
        result = Collection([])
        for item in payload:
            try:
                identifier = item["id"]
                if not isinstance(identifier, str) or any(
                    part in {".", ".."} for part in identifier.split("/")
                ):
                    raise ValueError("Invalid Hub ID")
                prefix = "datasets/" if family == "datasets" else ""
                tags = [tag for tag in item.get("tags", []) if isinstance(tag, str)][:80]
                body = "\n".join(
                    filter(
                        None, [item.get("description"), item.get("pipeline_tag"), ", ".join(tags)]
                    )
                )
                result.items.append(
                    RawItem(
                        platform_id=identifier,
                        title=identifier,
                        body=escape(body),
                        author=item.get("author"),
                        url=f"https://huggingface.co/{prefix}{quote(identifier, safe='/')}",
                        published_at=parse_time(item.get("createdAt")),
                        raw=item,
                        metrics={
                            "kind": "model" if family == "models" else "dataset",
                            "topics": tags,
                            "downloads": item.get("downloads"),
                            "likes": item.get("likes"),
                            "hub_trending_score": item.get("trendingScore"),
                            "updated_at": item.get("lastModified"),
                            "pipeline": item.get("pipeline_tag"),
                            "observed_at": now().isoformat(),
                        },
                    )
                )
            except (ValueError, TypeError, KeyError):
                result.errors.append("Hugging Face 资源字段无效，其他资源继续保存")
        return result
