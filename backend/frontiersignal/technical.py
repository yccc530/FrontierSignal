"""Explainable technical screening; rule scores are not model evaluations."""

import re
from dataclasses import dataclass

from .topics import PATTERNS, TOPICS

EVIDENCE = re.compile(
    r"\b(?:code|implementation|benchmark|experiment|architecture|weights|technical.report|model.card|paper|algorithm|inference|training|dataset|release|introducing|open.source|reproduc\w*)\b|源码|实验|基准|架构|开源|论文|技术报告|训练|发布",
    re.I,
)
NOISE = re.compile(
    r"\b(?:funding|fundrais\w*|valuation|stock.price|acquisition|celebrity|entertainment|marketing|sponsor\w*|giveaway|coupon|discount|earnings|lawsuit|election)\b|融资|估值|股价|娱乐|八卦|优惠券|营销|财报",
    re.I,
)
CATALOG = re.compile(
    r"(?:^|[/\s])(?:awesome[-_ ]|interview[-_ ]|roadmap|cheatsheet|prompt[-_ ]list)|curated list|资源合集|面试题",
    re.I,
)


@dataclass
class TechnicalSignal:
    score: int
    topics: list[str]
    reasons: list[str]
    eligible: bool


def technical_signal(
    title: str | None, body: str, kind: str, metrics: dict | None = None, trust: str | None = None
) -> TechnicalSignal:
    metrics = metrics or {}
    text = f"{title or ''}\n{body[:16000]}\n{' '.join(metrics.get('topics', []))}"
    topics = [key for key, pattern in PATTERNS.items() if pattern.search(text)]
    for topic in (metrics.get("model") or {}).get("topics", []):
        if topic in TOPICS and topic not in topics:
            topics.append(topic)
    if kind == "arxiv" and re.search(
        r"\b(?:machine.learning|neural|deep.learning|language.models?|generative)\b", text, re.I
    ):
        for topic, pattern in {
            "materials": r"\b(?:materials?|crystals?)\b",
            "biology": r"\b(?:protein|molecular|biological)\b",
        }.items():
            if re.search(pattern, text, re.I) and topic not in topics:
                topics.append(topic)
    if (
        kind not in {"hf_models", "arxiv"}
        and not re.search(
            r"\b(?:AI|diffusion|neural|generative|machine.learning|deep.learning|model|weights)\b|人工智能|模型|权重",
            text,
            re.I,
        )
        and not metrics.get("model")
    ):
        topics = [
            topic
            for topic in topics
            if topic not in {"image", "video", "audio", "cad", "knowledge_tools"}
        ]
    if re.search(r"\b(?:OpenAI|Claude Code)\b", text, re.I) and "llm" not in topics:
        topics.append("llm")
    if (
        topics == ["evaluation"]
        and kind != "arxiv"
        and not re.search(
            r"\b(?:AI|machine.learning|deep.learning|neural.network)\b|人工智能|机器学习",
            text,
            re.I,
        )
    ):
        topics = []
    if kind == "arxiv":
        ai_context = re.search(
            r"\b(?:AI|neural|deep.learning|machine.learning|language.model|diffusion|generative|reinforcement.learning|transformer|foundation.model)\b|人工智能|神经|机器学习|大模型",
            text,
            re.I,
        )
        if not ai_context:
            topics = [
                key for key in topics if key not in {"math", "materials", "biology", "evaluation"}
            ]
    if kind == "hf_datasets" and "training" not in topics:
        topics.append("training")
    evidence = set(match.group().casefold() for match in EVIDENCE.finditer(text))
    score = (15 + min(30, len(topics) * 10) + min(30, len(evidence) * 8)) if topics else 0
    if kind in {"arxiv", "hf_models", "hf_datasets"}:
        score += 15 if topics else 0
    if kind == "hf_models" and topics and (metrics.get("model") or {}).get("weight_file_count", 0):
        score += 15
    if kind in {"github", "github_discovery"} and metrics.get("language"):
        score += 10 if topics else 0
    if len(body) >= 100 and topics:
        score += 5
    concrete = bool(
        re.search(
            r"\b(?:sandbox|reasoning|inference|training|benchmark|scoring|access.control|framework|CLI|SDK|API|code|implementation|diffusion|speech.synthesis|text.to.video|text.to.image)\b|沙箱|推理|评测|训练|视频模型|语音模型",
            title or "",
            re.I,
        )
    )
    if kind == "hackernews" and topics and concrete:
        score += 20
    if trust == "official" and topics and evidence:
        score += 12
    reasons = [f"涉及{TOPICS[key][0]}" for key in topics[:3]]
    if evidence:
        reasons.append("原文包含技术方法、实现或评测线索")
    if NOISE.search(title or "") or (NOISE.search(text) and len(evidence) < 2):
        score -= 35
        reasons.append("商业或营销内容降权")
    if CATALOG.search(title or ""):
        score -= 25
        reasons.append("清单或资料汇编降权，尚不能证明有实现")
    if (
        "vibe_projects" in topics
        and (metrics.get("resource") or {}).get("vibe_status") != "author_declared"
    ):
        topics.remove("vibe_projects")
        reasons.append("AI 辅助开发方式尚无作者原文声明")
    if topics == ["agents"] and len(evidence) < 2:
        score = min(score, 40)
    if not topics:
        score = 0
    if metrics.get("archived") or metrics.get("fork"):
        score -= 40
        reasons.append("归档或派生仓库降权")
    score = max(0, min(100, score))
    if not topics:
        reasons.append("未发现目标技术主题")
    return TechnicalSignal(score, topics, reasons, score >= 45)
