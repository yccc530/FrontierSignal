"""Shared topic taxonomy. Registered topics do not imply collector coverage."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    label: str
    group: str
    pattern: str
    batch: int = 1
    github_query: str | None = None
    hf_tasks: tuple[str, ...] = ()
    hf_searches: tuple[str, ...] = ()
    arxiv_query: str | None = None
    dataset_searches: tuple[str, ...] = ()
    github_alternates: tuple[str, ...] = ()


CATALOG = {
    "llm": Topic(
        "大模型",
        "基础模型",
        r"\b(?:llms?|large language models?|language models?|gpt[- ]?\d|claude|gemini|llama|qwen|deepseek|mistral|text-generation|chatglm[ -]?\d*|glm[ -]?\d[\d.]*)(?:\b|_)|大模型|语言模型|智谱|智譜",
        github_query="topic:llm",
        hf_tasks=("text-generation", "text2text-generation"),
    ),
    "agents": Topic(
        "AI Agent",
        "工具与应用",
        r"\b(?:agentic|ai.agents?|multi.agents?|tool.calling|mcp|model context protocol|coding.agent)\b|智能体",
        github_query='"AI agent" in:name,description',
    ),
    "inference": Topic(
        "推理优化",
        "工程与研究",
        r"\b(?:inference|quantization|kv.cache|speculative.decoding|vllm|sglang|tensorrt|flash.attention|serving)\b|推理优化|量化|推理部署",
        github_query="topic:inference",
        arxiv_query='cat:cs.LG AND (all:"quantization" OR all:"speculative decoding")',
    ),
    "training": Topic(
        "训练与数据",
        "工程与研究",
        r"\b(?:fine.tun\w*|training|rlhf|lora|reinforcement.learning|distillation|datasets?|pretrain\w*)\b|微调|训练|蒸馏|数据集",
        github_query="topic:fine-tuning",
        arxiv_query='cat:cs.LG AND (all:"fine tuning" OR all:"distillation")',
        dataset_searches=("fine-tuning",),
    ),
    "rag": Topic(
        "RAG 与检索",
        "工程与研究",
        r"\b(?:rag|retrieval.augmented|embedding\w*|vector.search|rerank\w*)\b|检索增强|向量检索",
        github_query="topic:rag",
        arxiv_query='cat:cs.CL AND all:"retrieval augmented"',
        dataset_searches=("retrieval",),
    ),
    "multimodal": Topic(
        "多模态",
        "基础模型",
        r"\b(?:multimodal|multi.modal|vision.language|diffusion|computer.vision|image.generation|vlm|text.to.image|image.text.to.text|segment.anything|dinov\d+|sam[ -]?\d+|glm[\d.-]*v)\b|多模态|视觉模型",
        github_query="topic:multimodal",
        hf_tasks=("image-text-to-text", "visual-question-answering"),
    ),
    "evaluation": Topic(
        "评测与算法",
        "工程与研究",
        r"\b(?:benchmarks?|evaluat\w*|reasoning|algorithm\w*|machine.learning|neural.network\w*|deep.learning)\b|评测|基准|算法|机器学习",
        github_query="topic:machine-learning",
        arxiv_query='cat:cs.AI AND (all:"benchmark" OR all:"evaluation")',
        dataset_searches=("benchmark",),
    ),
    "frameworks": Topic(
        "开发框架",
        "工程与研究",
        r"\b(?:pytorch|transformers|langchain|llamaindex|hugging.face|ollama|jax|ai.framework\w*|model.context)\b|开发框架",
        github_query="topic:ai-framework",
    ),
    "coding_models": Topic(
        "代码模型",
        "基础模型",
        r"\b(?:coder|code.generation|code.models?|code.llm|code.completion|starcoder|codegemma|codestral)\b|代码模型|代码生成模型",
        2,
        '"code model" in:name,description',
        hf_searches=("coder",),
    ),
    "ocr": Topic(
        "OCR 与文档模型",
        "基础模型",
        r"\b(?:ocr|document.question.answering|document.understanding|document.parsing|image.to.text)\b|文档理解|文档解析|文字识别",
        2,
        '"OCR" "model" in:description',
        ("image-to-text", "document-question-answering"),
        ("OCR",),
    ),
    "image": Topic(
        "图像生成与编辑",
        "创作模型",
        r"\b(?:text.to.image|image.to.image|image.text.to.image|image.generation|image.editing|inpainting|outpainting|super.resolution|stable.diffusion|subject.consistency)\b|文生图|图像生成|图像编辑|超分辨率|图像修复|主体一致性",
        3,
        "topic:text-to-image",
        ("text-to-image", "image-to-image", "image-text-to-image"),
        ("inpainting", "super-resolution", "subject-consistency"),
    ),
    "video": Topic(
        "视频生成与编辑",
        "创作模型",
        r"\b(?:text.to.video|image.to.video|image.text.to.video|video.to.video|video.generation|video.diffusion|video.editing|camera.control|motion.control)\b|文生视频|图生视频|视频生成|视频编辑模型|镜头控制|动作控制模型",
        3,
        "topic:video-generation",
        ("text-to-video", "image-to-video", "image-text-to-video", "video-to-video"),
        ("video-editing", "camera-control"),
    ),
    "audio": Topic(
        "语音、音频与音乐",
        "创作模型",
        r"\b(?:text.to.speech|speech.to.text|automatic.speech.recognition|text.to.audio|audio.to.audio|audio.generation|music.generation|musicgen|sound.effects|speech.synthesis|speech.models?|voice.conversion|real.time.speech|streaming.tts)\b|语音合成|语音识别|音乐生成|音频模型|实时语音|音色转换|音效生成",
        3,
        "topic:text-to-speech",
        ("automatic-speech-recognition", "text-to-speech", "text-to-audio", "audio-to-audio"),
        ("musicgen", "realtime-speech", "sound-effects"),
    ),
    "3d": Topic(
        "3D 资产生成",
        "空间与设计",
        r"\b(?:text.to.3d|image.to.3d|3d.generation|3d.generative|neural.radiance|gaussian.splatting|neural.reconstruction|texture.generation)\b|三维生成|3D生成|3D 生成",
        4,
        "topic:3d-generation",
        ("text-to-3d", "image-to-3d"),
        ("Hunyuan3D", "TRELLIS"),
        arxiv_query='(cat:cs.CV OR cat:cs.GR) AND (all:"3D generation" OR all:"neural reconstruction")',
    ),
    "cad": Topic(
        "CAD 与工程设计",
        "空间与设计",
        r"\b(?:text.to.cad|text2cad|generative.cad|cad.models?|cad.generation|neural.cad)\b|参数化生成|CAD模型|CAD 模型",
        4,
        '"text-to-cad" in:name,description,readme',
        hf_searches=("Text2CAD", "text-to-cad"),
        arxiv_query='(cat:cs.CV OR cat:cs.AI) AND all:"CAD" AND (all:"generative" OR all:"language model")',
    ),
    "world_models": Topic(
        "世界模型",
        "空间与设计",
        r"\b(?:world.models?|generative.environments?)\b|世界模型",
        4,
        '"world model" in:name,description',
        hf_searches=("world-model", "Cosmos-Predict"),
        arxiv_query='(cat:cs.LG OR cat:cs.CV) AND all:"world model"',
    ),
    "robotics": Topic(
        "具身智能与机器人",
        "空间与设计",
        r"\b(?:embodied.ai|vision.language.action|robot.learning|robotic.foundation|robot.policy|openvla|diffusion.policy)\b|具身智能|机器人学习|机器人基础模型",
        4,
        "topic:vision-language-action",
        ("robotics",),
        ("OpenVLA", "diffusion-policy"),
        arxiv_query='cat:cs.RO AND (all:"vision language action" OR all:"robot learning")',
        dataset_searches=("lerobot",),
    ),
    "vibe_tools": Topic(
        "Vibe Coding 工具",
        "工具与应用",
        r"\b(?:vibe.coding|ai.coding.assistant|ai.code.editor|coding.agents?)\b|氛围编程|AI编程工具",
        5,
        '"coding agent" in:name,description',
        github_alternates=('"AI code editor" in:description',),
    ),
    "vibe_projects": Topic(
        "Vibe 项目案例",
        "工具与应用",
        r"\b(?:vibe.coded|vibecoded|built.with.ai|built.with.cursor|built.with.claude|ai.built.app)\b|用AI开发|AI辅助开发案例",
        5,
        "topic:vibe-coding",
        github_alternates=('"vibe coded" in:readme', '"built with AI" in:readme'),
    ),
    "ai_design": Topic(
        "AI 设计与前端生成",
        "工具与应用",
        r"\b(?:design.to.code|screenshot.to.code|ai.ui.generator|ai.design.tools?)\b|设计稿转代码|AI界面生成",
        5,
        '"screenshot-to-code" in:name,description',
        github_alternates=('"design-to-code" in:name,description', '"AI UI" in:description'),
    ),
    "creative_workflows": Topic(
        "AI 创作工作流",
        "工具与应用",
        r"\b(?:comfyui|generative.workflow|diffusion.workflow)\b|AI创作工作流",
        5,
        "topic:comfyui",
    ),
    "automation": Topic(
        "智能自动化",
        "工具与应用",
        r"\b(?:browser.agents?|computer.use|ai.automation|agentic.workflow|browser.use|desktop.agents?)\b|智能自动化|浏览器智能体",
        6,
        '"browser agent" in:name,description',
        github_alternates=('"computer use" in:description', '"browser use" in:description'),
    ),
    "mcp_skills": Topic(
        "MCP、Skills 与扩展",
        "工具与应用",
        r"\b(?:mcp.servers?|mcp.clients?|model.context.protocol|agent.skills?|claude.skills?)\b|智能体技能",
        6,
        "topic:mcp-server",
        github_alternates=(
            '"agent skills" in:name,description',
            '"claude skills" in:name,description',
        ),
    ),
    "dev_quality": Topic(
        "AI 开发质量工具",
        "工具与应用",
        r"\b(?:ai.code.review|llm.observability|agent.evaluation|ai.debugging|llm.cost|ai.testing|llm.tracing|context.engineering)\b|AI代码审查|智能体追踪",
        6,
        '"llm" "observability" in:name,description',
        github_alternates=('"AI code review" in:description', '"AI testing" in:description'),
    ),
    "local_apps": Topic(
        "本地模型应用",
        "工具与应用",
        r"\b(?:local.llm|on.device.ai|local.ai|llama.cpp|lm.studio)\b|本地模型|端侧模型",
        6,
        "topic:local-llm",
        github_alternates=('"on-device AI" in:description',),
    ),
    "knowledge_tools": Topic(
        "个人知识与研究工具",
        "工具与应用",
        r"\b(?:ai.research.assistant|ai.knowledge.base|local.rag|paper.qa|research.assistant|knowledge.base)\b|AI知识库|论文阅读助手",
        6,
        '"AI" "knowledge" in:description',
        github_alternates=('"AI research assistant" in:description',),
    ),
    "scientific": Topic(
        "AI 科学计算",
        "工程与研究",
        r"\b(?:ai.for.science|scientific.machine.learning|neural.operator|physics.informed)\b|AI科学计算|科学机器学习",
        7,
        '"neural operator" in:name,description',
        hf_searches=("neural-operator", "physics-informed"),
        arxiv_query='(cat:cs.LG OR cat:physics.comp-ph) AND (all:"neural operator" OR all:"physics informed")',
        dataset_searches=("physics",),
    ),
    "math": Topic(
        "数学推理",
        "工程与研究",
        r"\b(?:mathematical.reasoning|neural.theorem|ai.theorem|formal.reasoning|theorem.proving|deepseek.prover|qwen[\d.]*.math)\b|数学推理|自动定理证明",
        7,
        '"theorem proving" in:name,description',
        hf_searches=("DeepSeek-Prover", "Qwen-Math"),
        arxiv_query='(cat:cs.AI OR cat:cs.CL OR cat:cs.LO) AND (all:"mathematical reasoning" OR all:"theorem proving") AND (all:"neural" OR all:"language model")',
        dataset_searches=("math",),
    ),
    "materials": Topic(
        "AI 材料研究",
        "工程与研究",
        r"\b(?:materials.discovery|materials.foundation.model|ai.materials|crystal.generation|mattergen|mattersim)\b|AI材料|材料基础模型",
        7,
        '"materials" "machine learning" in:description',
        hf_searches=("MatterGen", "MatterSim"),
        arxiv_query='(cat:cond-mat.mtrl-sci OR cat:cs.LG) AND (all:"materials" OR all:"crystal") AND (all:"machine learning" OR all:"foundation model" OR all:"diffusion")',
        dataset_searches=("materials",),
    ),
    "biology": Topic(
        "AI 生物研究",
        "工程与研究",
        r"\b(?:protein.language.model|protein.structure.prediction|molecular.generation|biological.foundation.model|alphafold|esm[-_]?2[\w.-]*|boltz[-_]?2)\b|蛋白质模型|分子生成|生物基础模型",
        7,
        '"protein" "model" in:description',
        hf_searches=("ESM2", "protein"),
        arxiv_query='(cat:q-bio.BM OR cat:cs.LG) AND (all:"protein" OR all:"molecular") AND (all:"deep learning" OR all:"language model" OR all:"generative")',
        dataset_searches=("protein",),
    ),
}
TOPICS = {key: (value.label, value.pattern) for key, value in CATALOG.items()}
PATTERNS = {key: re.compile(value.pattern, re.I) for key, value in CATALOG.items()}
LEGACY_TOPICS = tuple(list(CATALOG)[:8])


def collection_topics(kind: str) -> list[str]:
    if kind == "github_discovery":
        return [key for key, value in CATALOG.items() if value.github_query]
    if kind == "hf_models":
        return [key for key, value in CATALOG.items() if value.hf_tasks or value.hf_searches]
    if kind == "arxiv":
        return [key for key, value in CATALOG.items() if value.arxiv_query]
    if kind == "hf_datasets":
        return [key for key, value in CATALOG.items() if value.dataset_searches]
    return []


def public_topics() -> list[dict]:
    return [
        {
            "id": key,
            "label": value.label,
            "group": value.group,
            "batch": value.batch,
            "discovery_ready": bool(value.github_query or value.hf_tasks or value.hf_searches),
            "collectors": [
                kind
                for kind in ("github_discovery", "hf_models", "hf_datasets", "arxiv")
                if key in collection_topics(kind)
            ],
        }
        for key, value in CATALOG.items()
    ]


def selected_topics(source, kind=None) -> list[str]:
    if (kind or source.kind) == "arxiv" and not (source.config or {}).get("research_queries"):
        return []
    available = collection_topics(kind or source.kind)
    selected = (source.config or {}).get("discovery_topics")
    return available if selected is None else [key for key in available if key in selected]
