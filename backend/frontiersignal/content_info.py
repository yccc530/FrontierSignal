"""Small, source-backed content descriptors. Declarations are never execution proof."""

import re
from urllib.parse import urlsplit

from .model_info import document_links, specification_quotes
from .topics import PATTERNS

RESOURCE_TYPES = {
    "tool": "开发工具",
    "project": "项目案例",
    "workflow": "创作工作流",
    "plugin": "插件 / 连接器",
    "framework": "运行框架",
    "client": "客户端",
    "application": "完整应用",
}
RESOURCE_QUOTES = {
    "host": r"\b(?:Claude.Desktop|Claude.Code|VS.Code|Visual.Studio.Code|Cursor|ComfyUI|MCP.clients?|host.application)\b|宿主",
    "authorization": r"\b(?:API.key|OAuth|permissions?|credentials|access.token|scopes?)\b|授权|权限|密钥",
    "purpose": r"\b(?:designed to|allows you|enables you|built for)\b|用于|用途",
    "dependencies": r"\b(?:requires?|dependencies|prerequisites|python\s*3|node.js)\b|依赖|要求",
    "input_output": r"\b(?:inputs?|outputs?|accepts|exports?)\b|输入|输出",
    "run": r"\b(?:installation|install with|getting started|run locally|quickstart)\b|安装|本地运行",
}
VIBE_CLAIM = re.compile(
    r"\b(?:vibe.coded|vibecoded|(?:built|developed|created)\s+(?:entirely\s+|primarily\s+)?"
    r"(?:with|using|by)\s+(?:AI|Cursor|Claude|Copilot|Codex))\b|(?:使用|借助|用)\s*AI.*(?:开发|制作)",
    re.I,
)
RESEARCH_QUOTES = {
    "claim": r"\b(?:we.propose|we.introduce|we.present|our.method|our.model)\b|本文提出|我们提出",
    "experiment": r"\b(?:experiments?|evaluated.on|training.setup|trained.on)\b|实验|训练设置",
    "benchmark": r"\b(?:benchmarks?|baselines?|evaluation.protocol|test.set)\b|基准|测试集",
    "reproduction": r"\b(?:code.is.available|implementation.is.available|reproducibility|reproduce)\b|代码已|复现",
}


def reference_identity(url):
    parsed = urlsplit(url or "")
    parts = parsed.path.strip("/").split("/")
    if (
        parsed.hostname in {"arxiv.org", "export.arxiv.org"}
        and len(parts) >= 2
        and parts[0] in {"abs", "pdf"}
    ):
        identifier = re.sub(r"v\d+$", "", parts[1].removesuffix(".pdf"))
        if re.fullmatch(r"\d{4}\.\d{4,5}", identifier):
            return f"paper:{identifier}"
    if parsed.hostname == "huggingface.co":
        if len(parts) == 3 and parts[0] == "datasets":
            return "dataset:" + "/".join(parts[1:]).casefold()
        if len(parts) == 2 and parts[0] not in {
            "docs",
            "blog",
            "spaces",
            "collections",
            "datasets",
        }:
            return "model:" + "/".join(parts).casefold()
    if parsed.hostname == "github.com" and len(parts) == 2:
        return "code:" + "/".join(parts).removesuffix(".git").casefold()
    return None


def reference_metadata(url, body):
    own = reference_identity(url)
    refs = []
    for link in document_links(body):
        identifier = reference_identity(link)
        if identifier and identifier != own and identifier not in {row["id"] for row in refs}:
            refs.append({"id": identifier, "kind": identifier.split(":")[0], "url": link})
    return {
        "identity_refs": [own] if own else [],
        "reference_refs": [r["id"] for r in refs[:16]],
        "references": refs[:16],
    }


def content_metadata(title, body, kind, metrics, url, *, readme=None, reference_body=None):
    result = dict(metrics or {})
    model = result.get("model") or {}
    reference_text = reference_body if reference_body is not None else body
    reference_text += "\n" + "\n".join(
        value for value in (model.get("code_url"), model.get("paper_url")) if value
    )
    reference_text += "\n" + "\n".join(
        "https://huggingface.co/" + ref for ref in result.get("model_references", [])
    )
    result.update(reference_metadata(url, reference_text))
    if kind == "arxiv":
        snippets = re.sub(r"(?<=[.!?])\s+(?=[A-Z])", "\n", body[:16000])
        result["kind"] = "paper"
        result["research"] = {
            "quotes": specification_quotes(snippets, url, patterns=RESEARCH_QUOTES) if url else [],
            "independent_replication": "unknown",
        }
        return result
    if kind not in {"github_discovery", "github"} or result.get("kind") == "release":
        return result
    resource = dict(result.get("resource") or {})
    text = f"{title or ''}\n{body[:30000]}"
    matched = {key for key, pattern in PATTERNS.items() if pattern.search(text)}
    source_url = resource.get("source_url") or url
    quotes = (
        specification_quotes(
            readme, source_url, resource.get("readme_sha"), patterns=RESOURCE_QUOTES
        )
        if source_url and readme is not None
        else resource.get("quotes", [])
    )
    claim = (
        next(
            (
                line.strip()[:600]
                for line in readme.splitlines()
                if len(line) <= 600
                and VIBE_CLAIM.search(line)
                and not re.search(r"\b(?:not|never|isn't|wasn't|no)\b|不是|并非|未经", line, re.I)
            ),
            None,
        )
        if resource.get("readme_sha") and readme is not None
        else ((resource.get("vibe_evidence") or {}).get("text"))
    )
    resource_type = (
        "plugin"
        if "mcp_skills" in matched
        or re.search(r"\b(?:plugin|extension|custom.nodes?)\b", text, re.I)
        else "workflow"
        if "creative_workflows" in matched
        else "framework"
        if re.search(
            r"\b(?:agent.framework|runtime.framework|AI.framework|SDK)\b", text[:2000], re.I
        )
        else "client"
        if "local_apps" in matched
        and re.search(r"\b(?:client|desktop|manager|GUI)\b", text[:2000], re.I)
        else "tool"
        if matched & {"vibe_tools", "ai_design", "dev_quality"}
        else "application"
        if matched & {"automation", "knowledge_tools", "local_apps"}
        else "project"
    )
    resource.update(
        {
            "type": resource_type,
            "label": RESOURCE_TYPES[resource_type],
            "vibe_status": "author_declared" if claim else "unverified",
            "vibe_evidence": {"text": claim, "source_url": source_url} if claim else None,
            "quotes": quotes,
            "execution_verified": False,
        }
    )
    result["resource"] = resource
    return result
