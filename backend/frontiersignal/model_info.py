"""Source-backed model metadata; lifecycle labels are source claims, not evaluations."""

import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from .normalizer import canonical_url
from .publishers import PUBLISHERS, publisher_evidence, publisher_for_author
from .topics import CATALOG, PATTERNS, collection_topics

HUB_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*")
MODEL_FAMILY = re.compile(
    r"\b(?:gpt|gemini|gemma|claude|qwen|deepseek|mistral|phi|llama|chatglm|glm)[ -]?(?:v)?\d", re.I
)
CREATIVE_FAMILIES = {
    "3d": re.compile(r"\b(?:hunyuan3d|trellis)(?:[. _-]|$)", re.I),
    "image": re.compile(
        r"\b(?:flux[. -]?\d|stable diffusion|imagen|qwen.image|cogview[\d.]*|glm.image)\b", re.I
    ),
    "video": re.compile(
        r"\b(?:sora|veo|wan[. -]?\d|hunyuanvideo|ltx[. -]?(?:video|\d)|cogvideox?[\d.-]*)\b", re.I
    ),
    "audio": re.compile(
        r"\b(?:whisper|stable audio|cosyvoice|ace.step|musicgen|qwen[\d.]*.tts|glm[\d.-]*.(?:voice|tts)|audiocraft|audiobox)\b",
        re.I,
    ),
    "multimodal": re.compile(
        r"\b(?:sam[ -]?\d|segment.anything|dinov\d|glm[\d.-]*v)(?:\b|[_-])", re.I
    ),
    "world_models": re.compile(r"\b(?:v[.-]?jepa[ -]?\d?|jepa.world)\b", re.I),
}
# Modalities describe the declared Hub task, not independently tested model capabilities.
MODEL_TASKS = {
    "text-to-3d": ("文本生成 3D", ("text",), ("3d",)),
    "image-to-3d": ("图像生成 3D", ("image",), ("3d",)),
    "text-generation": ("文本生成", ("text",), ("text",)),
    "text2text-generation": ("文本转换", ("text",), ("text",)),
    "image-text-to-text": ("图文理解", ("image", "text"), ("text",)),
    "visual-question-answering": ("视觉问答", ("image", "text"), ("text",)),
    "image-to-text": ("图像文字识别", ("image",), ("text",)),
    "document-question-answering": ("文档问答", ("image", "text"), ("text",)),
    "text-to-image": ("文生图", ("text",), ("image",)),
    "image-to-image": ("图像转换 / 编辑", ("image",), ("image",)),
    "image-text-to-image": ("图文编辑", ("image", "text"), ("image",)),
    "text-to-video": ("文生视频", ("text",), ("video",)),
    "image-to-video": ("图生视频", ("image",), ("video",)),
    "image-text-to-video": ("图文生成视频", ("image", "text"), ("video",)),
    "video-to-video": ("视频转换 / 编辑", ("video",), ("video",)),
    "automatic-speech-recognition": ("语音识别", ("audio",), ("text",)),
    "text-to-speech": ("语音合成", ("text",), ("audio",)),
    "text-to-audio": ("音频 / 音乐生成", ("text",), ("audio",)),
    "audio-to-audio": ("音频转换", ("audio",), ("audio",)),
}
SPEC_PATTERNS = {
    "output_format": r"\b(?:GLB|glTF|OBJ|PLY|STEP|STL|B-?rep|CADQuery)\b|输出格式",
    "editability": r"\b(?:parametric|editable|editability|parameterized|constructive.solid.geometry)\b|参数化|可编辑",
    "simulation": r"\b(?:simulation|simulator|sim.to.real|Isaac|MuJoCo|LIBERO)\b|仿真|模拟环境",
    "robot_hardware": r"\b(?:real.world.robot|real.robot|robot.hardware|Franka|UR5|ALOHA|SO.100|SO.101)\b|机械臂|真实机器人",
    "resolution": r"\b(?:\d{3,4}\s*[x×]\s*\d{3,4}|720p|1080p|2160p|4k)\b|resolution|分辨率",
    "duration": r"\b\d+(?:\.\d+)?[ -]*(?:seconds?|secs?|minutes?)\b|时长|\d+\s*秒",
    "frame_rate": r"\b\d+(?:\.\d+)?\s*(?:fps|frames per second)\b|帧率",
    "sample_rate": r"\b\d+(?:\.\d+)?\s*(?:khz|hz)\b|采样率",
    "hardware": r"\b(?:vram|gpu memory|cuda|rtx\s*\d+|[AH]100|[AH]200)\b|显存|硬件要求",
    "streaming": r"\b(?:streaming|real.time|latency)\b|流式|实时语音|延迟",
}


def model_topics(payload: dict) -> list[str]:
    card = payload.get("cardData") if isinstance(payload.get("cardData"), dict) else {}
    pipeline = payload.get("pipeline_tag") or card.get("pipeline_tag")
    text = " ".join([str(payload.get("id", "")), *[str(tag) for tag in payload.get("tags", [])]])
    result = [
        key
        for key, value in CATALOG.items()
        if pipeline in value.hf_tasks or (value.hf_searches and PATTERNS[key].search(text))
    ]
    identifier = str(payload.get("id", ""))
    _, publisher = publisher_for_author(identifier.split("/")[0])
    if publisher:
        if (
            "llm" not in result
            and "llm" in publisher.get("discovery_topics", collection_topics("hf_models"))
            and MODEL_FAMILY.search(identifier)
            and not pipeline
            and not any(pattern.search(identifier) for pattern in CREATIVE_FAMILIES.values())
            and not PATTERNS["ocr"].search(identifier)
        ):
            result.append("llm")
        for key, pattern in CREATIVE_FAMILIES.items():
            if (
                key not in result
                and pattern.search(identifier)
                and key in publisher.get("discovery_topics", collection_topics("hf_models"))
            ):
                result.append(key)
    return result


def model_metadata(payload: dict) -> dict:
    identifier = payload["id"]
    author = identifier.split("/")[0]
    publisher_id, publisher = publisher_for_author(author)
    card = payload.get("cardData") if isinstance(payload.get("cardData"), dict) else {}
    filenames = [
        row.get("rfilename", "") for row in payload.get("siblings", []) if isinstance(row, dict)
    ]
    weights = [
        name
        for name in filenames
        if re.search(r"\.(?:safetensors|gguf|pt|pth)$|(?:pytorch_model|model)[\w.-]*\.bin$", name)
    ]
    gated = payload.get("gated")
    access = (
        "gated_weights"
        if weights and gated
        else "public_weights"
        if weights and gated is False
        else "unknown"
    )
    license_name = (
        card.get("license_name")
        or card.get("license")
        or next(
            (
                tag.removeprefix("license:")
                for tag in payload.get("tags", [])
                if isinstance(tag, str) and tag.startswith("license:")
            ),
            None,
        )
    )
    task = payload.get("pipeline_tag") or card.get("pipeline_tag")
    task_info = MODEL_TASKS.get(task)
    return {
        "id": identifier,
        "publisher_id": publisher_id,
        "publisher": publisher["label"] if publisher else author,
        "publisher_verified": publisher is not None,
        "publisher_evidence": publisher_evidence(publisher, author) if publisher else None,
        "task": task,
        "task_label": task_info[0] if task_info else None,
        "modalities": {"inputs": list(task_info[1]), "outputs": list(task_info[2]), "basis": task}
        if task_info
        else None,
        "specifications": [],
        "topics": model_topics(payload),
        "version": str(card["version"])[:100] if card.get("version") else None,
        "revision": payload.get("sha"),
        "license": str(license_name)[:200] if license_name else None,
        "access": access,
        "gated": gated,
        "weight_files": weights[:8],
        "weight_file_count": len(weights),
        "hub_created_at": payload.get("createdAt"),
        "hub_updated_at": payload.get("lastModified"),
        "release_at": None,
        "release_status": "unknown",
        "release_evidence": None,
        "card_url": f"https://huggingface.co/{identifier}",
        "weights_url": f"https://huggingface.co/{identifier}/tree/main" if weights else None,
        "code_url": None,
        "paper_url": None,
        "card_status": "metadata_only",
        "references": [identifier.casefold()],
        "base_model": card.get("base_model"),
    }


def document_links(body: str) -> list[str]:
    links = (
        [tag.get("href") for tag in BeautifulSoup(body, "html.parser").find_all("a", href=True)]
        if "<" in body
        else []
    )
    links += [value.rstrip(".,;:") for value in re.findall(r"https://[^\s<>\]\)\"']+", body)]
    return list(
        dict.fromkeys(
            url for raw in links[:200] if (url := canonical_url(raw)) and url.startswith("https://")
        )
    )


def attach_model_links(model: dict, body: str) -> None:
    links = document_links(body)
    model["code_url"] = next(
        (
            url
            for url in links
            if urlsplit(url).hostname == "github.com"
            and len(urlsplit(url).path.strip("/").split("/")) == 2
        ),
        None,
    )
    model["paper_url"] = next(
        (
            url
            for url in links
            if urlsplit(url).hostname == "arxiv.org"
            and urlsplit(url).path.startswith(("/abs/", "/pdf/"))
        ),
        None,
    )


def specification_quotes(
    body: str, source_url: str, revision: str | None = None, *, patterns=None
) -> list[dict]:
    """Keep bounded source excerpts, never turn example settings into claimed maxima."""
    source_url = canonical_url(source_url)
    if not source_url or not source_url.startswith("https://"):
        return []
    snippets = {}
    fenced = False
    frontmatter = False
    lines = body[:30000].splitlines()
    for index, line in enumerate(lines):
        line = line.strip()
        if frontmatter:
            if line == "---":
                frontmatter = False
            continue
        # Stored originals can include a short header before the README's YAML.
        if (
            index < 16
            and line == "---"
            and any(re.match(r"[\w-]+:", value) for value in lines[index + 1 : index + 4])
        ):
            frontmatter = True
            continue
        if line.startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if (
            fenced
            or not 12 <= len(line) <= 600
            or line.startswith(("![", "<img", "<video", "<audio"))
        ):
            continue
        if re.match(r"(?:base_model|pipeline_tag|library_name|model-index|tags|datasets):", line):
            continue
        plain = (
            BeautifulSoup(line, "html.parser").get_text(" ", strip=True) if "<" in line else line
        )
        for key, pattern in (SPEC_PATTERNS if patterns is None else patterns).items():
            if key not in snippets and re.search(pattern, plain, re.I):
                snippets[key] = {
                    "kind": key,
                    "text": plain,
                    "source_url": source_url,
                    "revision": revision,
                }
    return list(snippets.values())


def attach_model_card(model: dict, body: str) -> None:
    attach_model_links(model, body)
    revision = model.get("card_revision")
    source_url = (
        f"{model['card_url']}/blob/{revision}/README.md"
        if revision and re.fullmatch(r"[a-fA-F0-9]{40}", revision)
        else model["card_url"]
    )
    model["specifications"] = specification_quotes(body, source_url, revision)


def annotate_official_model(item, source):
    publisher_id = (source.config or {}).get("publisher_id")
    if source.trust != "official" or publisher_id not in PUBLISHERS:
        return
    title = item.title or ""
    text = f"{title}\n{item.body}"
    refs = []
    for url in document_links(item.body):
        parsed = urlsplit(url)
        identifier = "/".join(parsed.path.strip("/").split("/")[:2])
        if (
            parsed.hostname == "huggingface.co"
            and HUB_ID.fullmatch(identifier)
            and not identifier.startswith(
                ("datasets/", "spaces/", "blog/", "docs/", "collections/")
            )
        ):
            refs.append(identifier.casefold())
    # Only explicit model release titles enter the model feed; other linked reports stay articles.
    creative = [key for key, pattern in CREATIVE_FAMILIES.items() if pattern.search(title)]
    model_title = (
        creative or MODEL_FAMILY.search(title) or re.search(r"\bmodel\b|模型", title, re.I)
    )
    action = re.search(
        r"introduc\w*|releas\w*|launch\w*|announc\w*|available|preview|update|发布|推出|更新|预览|上线|开源|built to",
        title,
        re.I,
    )
    if not model_title or not action:
        if refs:
            item.metrics["model_references"] = list(dict.fromkeys(refs))[:12]
        return
    status, evidence = "announcement", action.group()
    for phase, pattern in [
        ("preview", r"preview|预览|预告"),
        ("available", r"now available|generally available|正式上线|正式可用|现已开放"),
        ("update", r"updated?|升级|更新"),
    ]:
        match = re.search(pattern, title, re.I)
        if match:
            status, evidence = phase, match.group()
            break
    model = {
        "id": refs[0] if len(refs) == 1 else None,
        "references": list(dict.fromkeys(refs))[:12],
        "publisher_id": publisher_id,
        "publisher": PUBLISHERS[publisher_id]["label"],
        "publisher_verified": True,
        "publisher_evidence": source.url,
        "task": None,
        "version": None,
        "access": "unknown",
        "license": None,
        "release_status": status,
        "release_evidence": f"官方标题中的表述：{evidence}",
        "release_at": item.published_at.isoformat()
        if item.published_at and item.metrics.get("feed_time_kind") == "published"
        else None,
        "card_url": f"https://huggingface.co/{refs[0]}" if len(refs) == 1 else None,
        "weights_url": None,
        "card_status": "official_announcement",
        "topics": [key for key in collection_topics("hf_models") if PATTERNS[key].search(text)],
    }
    attach_model_links(model, item.body)
    model["specifications"] = specification_quotes(item.body, item.url) if item.url else []
    model["topics"] = list(dict.fromkeys([*model["topics"], *creative]))
    if not creative and MODEL_FAMILY.search(title) and "llm" not in model["topics"]:
        model["topics"].append("llm")
    item.metrics.update({"kind": "model_release", "model": model})
