"""Import one explicitly selected OpenCode provider into the private local configuration."""

import argparse
import json
import os
import re
from pathlib import Path

from dotenv import set_key
from frontiersignal.config import PROJECT_ROOT, Settings


def provider_values(path: Path, provider_name: str, model: str) -> dict[str, str]:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
        provider = config["provider"][provider_name]
        if model not in provider["models"]:
            raise ValueError
        options = provider["options"]
        address, key = options["baseURL"], options["apiKey"]
        if not isinstance(address, str) or not isinstance(key, str):
            raise ValueError
        reference = re.fullmatch(r"\{env:([A-Za-z_][A-Za-z0-9_]*)\}", key)
        if reference:
            key = os.environ.get(reference[1], "")
        if not key or key.startswith("{") or any(c in address + key + model for c in "\r\n"):
            raise ValueError
        address = Settings.validate_llm_url(address)
        if not address:
            raise ValueError
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError("无法读取指定网关和模型，请检查配置格式、地址及本地密钥") from None
    return {"FS_LLM_BASE_URL": address, "FS_LLM_API_KEY": key, "FS_LLM_MODEL": model}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path.home() / ".config/opencode/opencode.json"
    )
    parser.add_argument("--provider", default="火山AI网关")
    parser.add_argument("--model", default="volcengine/deepseek-v4.1-flash")
    parser.add_argument("--env-file", type=Path, default=PROJECT_ROOT / ".env")
    args = parser.parse_args()
    if not args.env_file.is_file():
        raise SystemExit("请先运行 scripts/setup.py 创建本地配置")
    try:
        values = provider_values(args.config.expanduser(), args.provider, args.model)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    args.env_file.chmod(0o600)
    for name, value in values.items():
        set_key(str(args.env_file), name, value, quote_mode="always")
    args.env_file.chmod(0o600)
    print(f"已导入指定网关，模型：{args.model}。密钥未输出；重启后端后生效。")


if __name__ == "__main__":
    main()
