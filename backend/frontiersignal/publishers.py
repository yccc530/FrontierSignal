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
        "author": None,
        "website": "https://developer.nvidia.com",
        "verification": "官方技术博客 RSS 已读取",
        "evidence_url": "https://developer.nvidia.com/blog/feed/",
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
        "discovery_topics": ["3d", "video", "image", "world_models"],
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
}
VERIFIED_AT = "2026-10-22"


def publisher_for_author(author):
    return next(
        (
            (key, value)
            for key, value in PUBLISHERS.items()
            if value["author"] and value["author"].casefold() == str(author).casefold()
        ),
        (None, None),
    )


def public_publishers():
    return [{"id": key, "verified_at": VERIFIED_AT, **value} for key, value in PUBLISHERS.items()]
