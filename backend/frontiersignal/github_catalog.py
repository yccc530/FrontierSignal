"""Reviewed repository/organization identities; membership is not a quality score."""

FIXED_REPOSITORIES = (
    ("comfyanonymous/ComfyUI", "创作工作流", ("Comfy-Org/ComfyUI",)),
    ("ggml-org/llama.cpp", "本地模型推理", ()),
    ("huggingface/diffusers", "扩散模型框架", ()),
    ("huggingface/transformers", "模型开发框架", ()),
    ("vllm-project/vllm", "模型推理服务", ()),
    ("sgl-project/sglang", "模型推理服务", ()),
    ("langchain-ai/langchain", "Agent 与应用框架", ()),
    ("run-llama/llama_index", "检索与知识应用", ()),
    ("microsoft/autogen", "多智能体框架", ()),
    ("crewAIInc/crewAI", "多智能体框架", ()),
    ("triton-lang/triton", "GPU 编程与编译", ()),
    ("microsoft/DeepSpeed", "模型训练与优化", ()),
    ("NVIDIA/Megatron-LM", "大模型训练", ()),
    ("ray-project/ray", "分布式训练与服务", ()),
    ("mlflow/mlflow", "模型开发与实验管理", ()),
    ("openai/openai-python", "模型服务 SDK", ()),
    ("anthropics/anthropic-sdk-python", "模型服务 SDK", ()),
)

# Each evidence page was read and contained a link to this exact GitHub account.
ORGANIZATIONS = (
    ("openai", "OpenAI", "https://platform.openai.com/docs/libraries"),
    ("anthropics", "Anthropic", "https://docs.anthropic.com/en/api/client-sdks"),
    ("google-deepmind", "Google DeepMind", "https://deepmind.google/"),
    ("facebookresearch", "Meta Research", "https://ai.meta.com/resources/models-and-libraries/"),
    ("QwenLM", "Qwen", "https://qwen.readthedocs.io/en/latest/"),
    ("deepseek-ai", "DeepSeek", "https://www.deepseek.com/"),
    ("huggingface", "Hugging Face", "https://huggingface.co/docs/transformers/index"),
    ("microsoft", "Microsoft", "https://opensource.microsoft.com/"),
    ("mistralai", "Mistral AI", "https://docs.mistral.ai/"),
    ("NVIDIA", "NVIDIA", "https://developer.nvidia.com/tensorrt"),
)


def fixed_repository(name):
    for canonical, label, aliases in FIXED_REPOSITORIES:
        if name.casefold() in {value.casefold() for value in (canonical, *aliases)}:
            return {
                "kind": "fixed",
                "catalog_name": canonical,
                "label": label,
                "evidence_url": f"https://github.com/{canonical}",
                "basis": "维护者登记的常用基础设施；不代表近期增长或独立质量核验",
            }
    return None


def organization_identity(owner):
    for login, label, evidence in ORGANIZATIONS:
        if str(owner or "").casefold() == login.casefold():
            return {
                "login": login,
                "label": label,
                "evidence_url": evidence,
                "verified_at": "2026-11-05",
                "basis": "已读取官网页面的明确 GitHub 链接；仅核验账号身份",
            }
    return None


def public_github_catalog():
    return {
        "fixed_repositories": [
            {
                "name": name,
                "label": label,
                "aliases": list(aliases),
                "evidence_url": f"https://github.com/{name}",
            }
            for name, label, aliases in FIXED_REPOSITORIES
        ],
        "organizations": [organization_identity(login) for login, _, _ in ORGANIZATIONS],
        "quality_verified": False,
    }
