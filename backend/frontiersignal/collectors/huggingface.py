import re
from html import escape
from urllib.parse import quote, urlencode

from ..discovery_state import record_scan
from ..model_info import HUB_ID, attach_model_card, model_metadata, model_topics
from ..models import Source, now
from ..network import FetchError
from ..normalizer import RawItem
from ..projects import parse_time
from ..publishers import PUBLISHERS
from ..topics import CATALOG, selected_topics
from .base import Collection


def model_groups(source):
    topics = selected_topics(source, "hf_models")
    groups = [
        {
            "id": "global:trending",
            "label": "全站热门补充",
            "topics": topics,
            "params": {},
            "lane": "global",
        }
    ]
    for key in topics:
        topic = CATALOG[key]
        for task in topic.hf_tasks:
            groups.append(
                {
                    "id": f"topic:{key}:{task}",
                    "label": f"{topic.label} · {task}",
                    "topics": [key],
                    "params": {"pipeline_tag": task},
                    "lane": "topic",
                }
            )
        for search in topic.hf_searches:
            groups.append(
                {
                    "id": f"topic:{key}:search"
                    + (f":{search}" if len(topic.hf_searches) > 1 else ""),
                    "label": f"{topic.label} · {search}",
                    "topics": [key],
                    "params": {"search": search},
                    "lane": "topic",
                }
            )
    for key, publisher in PUBLISHERS.items():
        supported = [key for key in topics if key in publisher.get("discovery_topics", topics)]
        if publisher["author"] and supported:
            groups.append(
                {
                    "id": f"publisher:{key}",
                    "label": publisher["label"],
                    "topics": supported,
                    "params": {"author": publisher["author"]},
                    "lane": "publisher",
                }
            )
    return groups


def model_query(source, tick, limit):
    groups = model_groups(source)
    lanes = ("global", "topic", "publisher", "topic", "topic", "topic")
    lane = lanes[tick % len(lanes)]
    choices = [group for group in groups if group["lane"] == lane]
    if not choices:
        raise ValueError("模型来源没有启用的采集方向")
    cycle = tick // len(lanes) * lanes.count(lane) + lanes[: tick % len(lanes)].count(lane)
    if lane == "topic":
        # Give each topic an equal turn before rotating through its task/keyword queries.
        topics = list(dict.fromkeys(group["topics"][0] for group in choices))
        topic = topics[cycle % len(topics)]
        choices = [group for group in choices if group["topics"] == [topic]]
        cycle //= len(topics)
    group = choices[cycle % len(choices)]
    rotation = cycle // len(choices)
    params = {
        "sort": "trendingScore"
        if lane == "global"
        else ("createdAt", "lastModified", "trendingScore")[rotation % 3],
        "direction": -1,
        "limit": limit,
        "full": "true",
        "cardData": "true",
        **group["params"],
    }
    # Author queries discover that team's actual tasks; scope is checked on each returned model.
    return group, params


class HuggingFaceCollector:
    def __init__(self, fetcher):
        self.fetcher = fetcher
        self.known_cards: dict[str, dict] = {}

    async def collect(self, source):
        if source.kind == "hf_datasets":
            return await self.datasets(source)
        config = self.fetcher.settings
        cursor = source.cursor or {}
        tick = cursor.get("model_tick", 0)
        tick = tick if isinstance(tick, int) and tick >= 0 else 0
        scans = dict(cursor.get("scans", {}))
        result = Collection([], advance_on_partial=True)
        observations = {}
        priorities = {}
        memberships = {}
        responses = {}
        for step in range(config.hf_queries_per_run):
            group, params = model_query(
                source, tick + step, min(config.hf_candidates_per_query, config.max_items)
            )
            try:
                url = "https://huggingface.co/api/models?" + urlencode(params)
                if url not in responses:
                    responses[url] = await self.fetcher.json(url)
                payload = responses[url]
                if not isinstance(payload, list):
                    raise ValueError("模型列表格式无效")
                rejected = 0
                for row in payload:
                    if (
                        not isinstance(row, dict)
                        or not HUB_ID.fullmatch(str(row.get("id", "")))
                        or row.get("private") is True
                    ):
                        rejected += 1
                        continue
                    matched = model_topics(row)
                    if (
                        params.get("author")
                        and row["id"].split("/")[0].casefold() != params["author"].casefold()
                    ):
                        result.filtered += 1
                        continue
                    # Keep the legacy broad feed unless the user explicitly narrows its scope.
                    if (
                        group["lane"] != "global"
                        or (source.config or {}).get("discovery_topics") is not None
                    ) and not set(matched) & set(group["topics"]):
                        result.filtered += 1
                        continue
                    observations[row["id"]] = row
                    memberships.setdefault(row["id"], set()).add(group["id"])
                    priority = {"publisher": 0, "topic": 1, "global": 2}[group["lane"]]
                    priorities[row["id"]] = min(priority, priorities.get(row["id"], priority))
                error = f"{rejected} 条模型记录格式无效" if rejected else None
                record_scan(
                    scans,
                    group["id"],
                    label=group["label"],
                    topics=group["topics"],
                    count=len(payload),
                    error=error,
                    partial=True,
                )
                scans[group["id"]]["query"] = params
                if error:
                    result.errors.append(f"{group['label']}：{error}")
            except Exception as exc:
                error = (
                    f"模型查询失败（HTTP {exc.status}）"
                    if isinstance(exc, FetchError) and exc.status
                    else f"模型查询失败（{type(exc).__name__}）"
                )
                record_scan(
                    scans, group["id"], label=group["label"], topics=group["topics"], error=error
                )
                result.errors.append(f"{group['label']}：{error}")
        card_checks = 0
        candidates = sorted(observations.items(), key=lambda pair: priorities[pair[0]])
        for identifier, payload in candidates[: config.max_items]:
            try:
                model = model_metadata(payload)
                body = ""
                previous = self.known_cards.get(identifier, {})
                revision = model["revision"]
                has_readme = any(
                    row.get("rfilename") == "README.md"
                    for row in payload.get("siblings", [])
                    if isinstance(row, dict)
                )
                if (
                    revision
                    and previous.get("card_revision") == revision
                    and previous.get("card_status") in {"available", "cached"}
                ):
                    model["card_status"] = "cached"
                elif (
                    has_readme
                    and card_checks < config.hf_card_checks
                    and isinstance(revision, str)
                    and re.fullmatch(r"[a-fA-F0-9]{40}", revision)
                ):
                    card_checks += 1
                    try:
                        content, _, _ = await self.fetcher.get(
                            f"https://huggingface.co/{quote(identifier, safe='/')}/resolve/{revision}/README.md"
                        )
                        body = content.decode("utf-8", errors="replace")[:30000]
                        model.update(
                            {
                                "card_status": "available",
                                "card_revision": revision,
                                "card_observed_at": now().isoformat(),
                                "card_truncated": len(content.decode("utf-8", errors="replace"))
                                > 30000,
                            }
                        )
                        attach_model_card(model, body)
                    except Exception as exc:
                        model["card_status"] = "unavailable"
                        result.errors.append(
                            f"{identifier} 模型卡不可读（{type(exc).__name__}）；元数据保留"
                        )
                header = f"模型仓库：{identifier}\n任务：{model['task'] or '未声明'}\n许可证声明：{model['license'] or '未声明'}"
                tags = [tag for tag in payload.get("tags", []) if isinstance(tag, str)][:80]
                text = (
                    f"{header}\n标签：{', '.join(sorted(set(tags)))}\n{body}"
                    if body
                    else f"{header}\n{', '.join(sorted(set(tags)))}"
                )
                result.items.append(
                    RawItem(
                        platform_id=identifier,
                        title=identifier,
                        body=escape(text),
                        author=identifier.split("/")[0],
                        url=f"https://huggingface.co/{quote(identifier, safe='/')}",
                        published_at=None,
                        preserve_existing_content=model["card_status"] != "available",
                        raw={
                            "api": payload,
                            "model_card": body or None,
                            "card_status": model["card_status"],
                            "card_revision": model.get("card_revision"),
                            "card_truncated": model.get("card_truncated", False),
                        },
                        metrics={
                            "kind": "model",
                            "topics": tags,
                            "model": model,
                            "downloads": payload.get("downloads"),
                            "likes": payload.get("likes"),
                            "hub_trending_score": payload.get("trendingScore"),
                            "pipeline": payload.get("pipeline_tag"),
                            "updated_at": payload.get("lastModified"),
                            "observed_at": now().isoformat(),
                        },
                    )
                )
            except (ValueError, TypeError, KeyError, AttributeError):
                result.errors.append(f"{identifier} 模型字段无效，其他模型继续保存")
        for item in result.items:
            item.metrics["discovery_groups"] = sorted(memberships.get(item.platform_id, []))
        result.cursor = {
            "model_tick": tick + config.hf_queries_per_run,
            "scans": {
                key: value
                for key, value in scans.items()
                if key
                in {group["id"] for group in model_groups(Source(kind="hf_models", config={}))}
            },
        }
        return result

    async def datasets(self, source):
        groups = dataset_groups(source)
        tick = (source.cursor or {}).get("dataset_tick", 0)
        scans = dict((source.cursor or {}).get("scans", {}))
        result = Collection([], advance_on_partial=True)
        observations = {}
        memberships = {}
        steps = min(3, len(groups))
        for step in range(steps):
            group = groups[(tick + step) % len(groups)]
            params = {
                "sort": "trendingScore" if not group["topics"] else "lastModified",
                "direction": -1,
                "limit": min(10, self.fetcher.settings.max_items),
                "full": "true",
                **group["params"],
            }
            try:
                payload = await self.fetcher.json(
                    "https://huggingface.co/api/datasets?" + urlencode(params)
                )
                if not isinstance(payload, list):
                    raise ValueError("Hugging Face 返回的资源列表格式异常")
                for item in payload:
                    if not isinstance(item, dict) or not HUB_ID.fullmatch(str(item.get("id", ""))):
                        raise ValueError("Invalid dataset ID")
                    if not item.get("private"):
                        observations[item["id"]] = item
                        memberships.setdefault(item["id"], set()).add(group["id"])
                record_scan(
                    scans,
                    group["id"],
                    label=group["label"],
                    topics=group["topics"],
                    count=len(payload),
                )
            except Exception as exc:
                error = f"HF 数据集查询失败（{type(exc).__name__}）"
                result.errors.append(error)
                record_scan(
                    scans, group["id"], label=group["label"], topics=group["topics"], error=error
                )
        payload = list(observations.values())[: self.fetcher.settings.max_items]
        for item in payload:
            try:
                identifier = item["id"]
                if not HUB_ID.fullmatch(identifier):
                    raise ValueError("Invalid Hub ID")
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
                        url=f"https://huggingface.co/datasets/{quote(identifier, safe='/')}",
                        published_at=parse_time(item.get("createdAt")),
                        raw=item,
                        metrics={
                            "kind": "dataset",
                            "discovery_groups": sorted(memberships.get(identifier, [])),
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
        result.cursor = {"dataset_tick": tick + steps, "scans": scans}
        return result


def dataset_groups(source):
    return [{"id": "global:datasets", "label": "热门数据集补充", "topics": [], "params": {}}] + [
        {
            "id": f"dataset:{key}:{search}",
            "label": f"{CATALOG[key].label} · {search}",
            "topics": [key],
            "params": {"search": search},
        }
        for key in selected_topics(source, "hf_datasets")
        for search in CATALOG[key].dataset_searches
    ]
