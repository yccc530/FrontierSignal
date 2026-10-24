"""Reviewed publisher identities, not a claim of complete product coverage."""

PUBLISHERS = {
    "openai": {
        "label": "OpenAI",
        "author": "openai",
        "website": "https://openai.com",
        "verification": "Hub 已认证组织",
        "evidence_url": "https://huggingface.co/api/organizations/openai/overview",
    },
    "google": {
        "label": "Google",
        "author": "google",
        "website": "https://deepmind.google",
        "verification": "Hub 已认证组织",
        "evidence_url": "https://huggingface.co/api/organizations/google/overview",
    },
    "qwen": {
        "label": "阿里 Qwen",
        "author": "Qwen",
        "website": "https://qwen.ai",
        "verification": "官方文档链接至同名 Hub 组织",
        "evidence_url": "https://qwen.readthedocs.io/en/latest/",
    },
    "deepseek": {
        "label": "DeepSeek",
        "author": "deepseek-ai",
        "website": "https://www.deepseek.com",
        "verification": "Hub 已认证组织",
        "evidence_url": "https://huggingface.co/api/organizations/deepseek-ai/overview",
    },
    "mistral": {
        "label": "Mistral AI",
        "author": "mistralai",
        "website": "https://mistral.ai",
        "verification": "Hub 已认证组织",
        "evidence_url": "https://huggingface.co/api/organizations/mistralai/overview",
    },
    "microsoft": {
        "label": "Microsoft",
        "author": "microsoft",
        "website": "https://www.microsoft.com",
        "verification": "Hub 已认证组织",
        "evidence_url": "https://huggingface.co/api/organizations/microsoft/overview",
    },
    "nvidia": {
        "label": "NVIDIA",
        "author": "nvidia",
        "website": "https://developer.nvidia.com",
        "verification": "Hub 已认证组织；官方技术博客独立采集",
        "evidence_url": "https://huggingface.co/api/organizations/nvidia/overview",
        "verified_at": "2026-10-24",
    },
    "bfl": {
        "label": "Black Forest Labs",
        "author": "black-forest-labs",
        "website": "https://bfl.ai",
        "verification": "Hub 已认证组织",
        "evidence_url": "https://huggingface.co/api/organizations/black-forest-labs/overview",
        "verified_at": "2026-10-23",
        "discovery_topics": ["image"],
    },
    "stability": {
        "label": "Stability AI",
        "author": "stabilityai",
        "website": "https://stability.ai",
        "verification": "官方代码仓库链接至同名 Hub 模型",
        "evidence_url": "https://github.com/Stability-AI/stable-audio-tools",
        "verified_at": "2026-10-23",
        "discovery_topics": ["image", "audio"],
    },
    "wan": {
        "label": "阿里 Wan",
        "author": "Wan-AI",
        "website": "https://github.com/Wan-Video/Wan2.2",
        "verification": "官方代码仓库链接至同名 Hub 组织",
        "evidence_url": "https://github.com/Wan-Video/Wan2.2",
        "verified_at": "2026-10-23",
        "discovery_topics": ["video"],
    },
    "lightricks": {
        "label": "Lightricks",
        "author": "Lightricks",
        "website": "https://github.com/Lightricks/LTX-Video",
        "verification": "官方代码仓库链接至同名 Hub 模型",
        "evidence_url": "https://github.com/Lightricks/LTX-Video",
        "verified_at": "2026-10-23",
        "discovery_topics": ["video"],
    },
    "funaudio": {
        "label": "FunAudioLLM",
        "author": "FunAudioLLM",
        "website": "https://github.com/FunAudioLLM/CosyVoice",
        "verification": "官方代码仓库链接至同名 Hub 模型",
        "evidence_url": "https://github.com/FunAudioLLM/CosyVoice",
        "verified_at": "2026-10-23",
        "discovery_topics": ["audio"],
    },
    "acestep": {
        "label": "ACE-Step",
        "author": "ACE-Step",
        "website": "https://github.com/ACE-Step/ACE-Step",
        "verification": "官方代码仓库链接至同名 Hub 模型",
        "evidence_url": "https://github.com/ACE-Step/ACE-Step",
        "verified_at": "2026-10-23",
        "discovery_topics": ["audio"],
    },
    "tencent": {
        "label": "腾讯 Hunyuan",
        "author": "tencent",
        "website": "https://github.com/Tencent-Hunyuan",
        "verification": "Hub 已认证组织",
        "evidence_url": "https://huggingface.co/api/organizations/tencent/overview",
        "verified_at": "2026-10-23",
        "discovery_topics": [
            "llm",
            "coding_models",
            "multimodal",
            "3d",
            "video",
            "image",
            "audio",
            "world_models",
        ],
    },
    "openvla": {
        "label": "OpenVLA",
        "author": "openvla",
        "website": "https://github.com/openvla/openvla",
        "verification": "项目代码仓库 README 明确链接至同名 Hub 模型",
        "evidence_url": "https://github.com/openvla/openvla",
        "verified_at": "2026-10-23",
        "discovery_topics": ["robotics"],
    },
    "zai": {
        "label": "智谱 / Z.ai",
        "author": "zai-org",
        "website": "https://z.ai",
        "verification": "官方 GLM 仓库 README 链接至该 Hub 组织；不代表 Hub 认证徽标",
        "evidence_url": "https://github.com/zai-org/GLM-4.5",
        "verified_at": "2026-10-23",
        "priority": True,
        "discovery_topics": [
            "llm",
            "coding_models",
            "multimodal",
            "ocr",
            "image",
            "video",
            "audio",
        ],
    },
    "meta": {
        "label": "Meta",
        "author": "meta-llama",
        "additional_authors": ["facebook"],
        "website": "https://ai.meta.com",
        "verification": "两个账号均为 Hub 已认证组织",
        "evidence_url": "https://huggingface.co/api/organizations/meta-llama/overview",
        "author_evidence": {
            "facebook": "https://huggingface.co/api/organizations/facebook/overview",
        },
        "verified_at": "2026-10-23",
        "priority": True,
        "discovery_topics": [
            "llm",
            "coding_models",
            "multimodal",
            "image",
            "video",
            "audio",
            "world_models",
            "robotics",
        ],
    },
    "kimi": {
        "label": "月之暗面 Kimi",
        "author": "moonshotai",
        "region": "china",
        "website": "https://www.kimi.com",
        "verification": "官方 Kimi-K2 仓库链接至该 Hub 组织",
        "evidence_url": "https://github.com/moonshotai/Kimi-K2",
        "verified_at": "2026-10-24",
        "discovery_topics": ["llm", "coding_models", "multimodal"],
    },
    "minimax": {
        "label": "MiniMax",
        "author": "MiniMaxAI",
        "region": "china",
        "website": "https://www.minimax.io",
        "verification": "官方 MiniMax-M2 仓库链接至该 Hub 组织",
        "evidence_url": "https://github.com/MiniMax-AI/MiniMax-M2",
        "verified_at": "2026-10-24",
        "discovery_topics": ["llm", "coding_models", "audio", "video", "multimodal"],
    },
    "stepfun": {
        "label": "阶跃星辰 StepFun",
        "author": "stepfun-ai",
        "region": "china",
        "website": "https://www.stepfun.com",
        "verification": "官方 Step-3.5-Flash 仓库链接至该 Hub 组织",
        "evidence_url": "https://github.com/stepfun-ai/Step-3.5-Flash",
        "verified_at": "2026-10-24",
        "discovery_topics": ["llm", "coding_models", "multimodal", "image", "video", "audio"],
    },
    "baidu": {
        "label": "百度 ERNIE / Paddle",
        "author": "baidu",
        "region": "china",
        "additional_authors": ["PaddlePaddle"],
        "website": "https://www.baidu.com",
        "verification": "两个账号均为 Hub 已认证组织",
        "evidence_url": "https://huggingface.co/api/organizations/baidu/overview",
        "author_evidence": {
            "PaddlePaddle": "https://huggingface.co/api/organizations/PaddlePaddle/overview"
        },
        "verified_at": "2026-10-24",
        "discovery_topics": ["llm", "multimodal", "ocr", "audio", "image"],
    },
    "intern": {
        "label": "上海 AI Lab · Intern",
        "author": "internlm",
        "region": "china",
        "additional_authors": ["OpenGVLab"],
        "website": "https://www.intern-ai.org.cn",
        "verification": "InternLM 与 InternVL 官方仓库分别链接至对应 Hub 组织",
        "evidence_url": "https://github.com/InternLM/InternLM",
        "author_evidence": {"OpenGVLab": "https://github.com/OpenGVLab/InternVL"},
        "verified_at": "2026-10-24",
        "discovery_topics": ["llm", "multimodal", "coding_models", "video", "robotics"],
    },
    "bytedance": {
        "label": "字节 Seed",
        "author": "ByteDance-Seed",
        "region": "china",
        "website": "https://seed.bytedance.com",
        "verification": "官方 Seed-OSS 仓库链接至该 Hub 组织的模型集合",
        "evidence_url": "https://github.com/bytedance-seed/Seed-OSS",
        "verified_at": "2026-10-24",
        "discovery_topics": [
            "llm",
            "coding_models",
            "multimodal",
            "image",
            "video",
            "audio",
            "robotics",
        ],
    },
    "anthropic": {
        "label": "Anthropic · Claude",
        "author": None,
        "region": "global",
        "website": "https://www.anthropic.com",
        "verification": "官方新闻页与 robots 声明的站点地图",
        "evidence_url": "https://www.anthropic.com/robots.txt",
        "verified_at": "2026-10-24",
    },
    "cohere": {
        "label": "Cohere",
        "author": "CohereLabs",
        "region": "global",
        "website": "https://cohere.com",
        "verification": "Hub 已认证组织；官方博客独立采集",
        "evidence_url": "https://huggingface.co/api/organizations/CohereLabs/overview",
        "verified_at": "2026-10-24",
        "discovery_topics": ["llm", "multimodal", "rag", "coding_models"],
    },
    "amazon": {
        "label": "Amazon · Nova",
        "author": "amazon",
        "region": "global",
        "website": "https://aws.amazon.com",
        "verification": "Hub 已认证组织；AWS 官方 RSS",
        "evidence_url": "https://huggingface.co/api/organizations/amazon/overview",
        "verified_at": "2026-10-24",
    },
    "xai": {
        "label": "xAI · Grok",
        "author": "xai-org",
        "region": "global",
        "website": "https://x.ai",
        "verification": "Hub 已认证组织；发布页当前 403，未启用自动采集",
        "evidence_url": "https://huggingface.co/api/organizations/xai-org/overview",
        "verified_at": "2026-10-24",
        "discovery_topics": ["llm", "multimodal", "coding_models"],
    },
}
VERIFIED_AT = "2026-10-22"


def publisher_authors(publisher):
    return (
        [publisher["author"], *publisher.get("additional_authors", [])]
        if publisher["author"]
        else []
    )


def publisher_for_author(author):
    return next(
        (
            (key, value)
            for key, value in PUBLISHERS.items()
            if str(author).casefold() in {name.casefold() for name in publisher_authors(value)}
        ),
        (None, None),
    )


def publisher_evidence(publisher, author):
    return next(
        (
            url
            for name, url in publisher.get("author_evidence", {}).items()
            if name.casefold() == str(author).casefold()
        ),
        publisher["evidence_url"],
    )


def public_publishers():
    domestic = {"qwen", "deepseek", "wan", "funaudio", "tencent", "zai"}
    return [
        {
            "id": key,
            "verified_at": VERIFIED_AT,
            "region": "china" if key in domestic else "global",
            **value,
        }
        for key, value in PUBLISHERS.items()
    ]
