"""Explainable technical screening; rule scores are not model evaluations."""

import re
from dataclasses import dataclass

TOPICS = {
    "llm": (
        "大模型",
        r"\b(?:llms?|large language models?|language models?|gpt[- ]?\d|claude|gemini|llama|qwen|deepseek|mistral|text-generation)\b|大模型|语言模型",
    ),
    "agents": (
        "AI Agent",
        r"\b(?:agentic|ai.agents?|multi.agents?|tool.calling|mcp|model context protocol|coding.agent)\b|智能体",
    ),
    "inference": (
        "推理优化",
        r"\b(?:inference|quantization|kv.cache|speculative.decoding|vllm|sglang|tensorrt|flash.attention|serving)\b|推理优化|量化|推理部署",
    ),
    "training": (
        "训练与数据",
        r"\b(?:fine.tun\w*|training|rlhf|lora|reinforcement.learning|distillation|datasets?|pretrain\w*)\b|微调|训练|蒸馏|数据集",
    ),
    "rag": (
        "RAG 与检索",
        r"\b(?:rag|retrieval.augmented|embedding\w*|vector.search|rerank\w*)\b|检索增强|向量检索",
    ),
    "multimodal": (
        "多模态",
        r"\b(?:multimodal|multi.modal|vision.language|diffusion|computer.vision|image.generation|vlm|text.to.image)\b|多模态|视觉模型",
    ),
    "evaluation": (
        "评测与算法",
        r"\b(?:benchmarks?|evaluat\w*|reasoning|algorithm\w*|machine.learning|neural.network\w*|deep.learning)\b|评测|基准|算法|机器学习",
    ),
    "frameworks": (
        "开发框架",
        r"\b(?:pytorch|transformers|langchain|llamaindex|hugging.face|ollama|jax|ai.framework\w*|model.context)\b|开发框架",
    ),
}
PATTERNS = {key: re.compile(pattern, re.I) for key, (_, pattern) in TOPICS.items()}
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
    if kind == "arxiv" and not topics:
        topics = ["evaluation"]
    if kind == "hf_datasets" and "training" not in topics:
        topics.append("training")
    evidence = set(match.group().casefold() for match in EVIDENCE.finditer(text))
    score = (15 + min(30, len(topics) * 10) + min(30, len(evidence) * 8)) if topics else 0
    if kind in {"arxiv", "hf_models", "hf_datasets"}:
        score += 15 if topics else 0
    if kind in {"github", "github_discovery"} and metrics.get("language"):
        score += 10 if topics else 0
    if len(body) >= 100 and topics:
        score += 5
    concrete = bool(
        re.search(
            r"\b(?:sandbox|reasoning|inference|training|benchmark|scoring|access.control|framework|CLI|SDK|API|code|implementation)\b|沙箱|推理|评测|训练",
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
    if (
        NOISE.search(title or "")
        or re.search(r"\b(?:pokemon|browser.games|giveaway)\b", title or "", re.I)
        or (NOISE.search(text) and len(evidence) < 2)
    ):
        score -= 35
        reasons.append("商业或营销内容降权")
    if CATALOG.search(title or ""):
        score -= 25
        reasons.append("清单或资料汇编降权，尚不能证明有实现")
    if metrics.get("archived") or metrics.get("fork"):
        score -= 40
        reasons.append("归档或派生仓库降权")
    score = max(0, min(100, score))
    if not topics:
        reasons.append("未发现目标技术主题")
    return TechnicalSignal(score, topics, reasons, score >= 45)
