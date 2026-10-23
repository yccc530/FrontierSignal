import json
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/configure_opencode.py"


def run_import(tmp_path, model="volcengine/deepseek-v4.1-flash"):
    config = tmp_path / "opencode.json"
    original = json.dumps(
        {
            "provider": {
                "火山AI网关": {
                    "options": {
                        "baseURL": "https://gateway.example/v1",
                        "apiKey": "fixture-private-key",
                    },
                    "models": {
                        "volcengine/deepseek-v4.1-flash": {"name": "DeepSeek-V4.1-Flash1017"}
                    },
                }
            }
        },
        ensure_ascii=False,
    )
    config.write_text(original, encoding="utf-8")
    destination = tmp_path / ".env"
    destination.write_text(
        "FS_DATABASE_URL=existing-database\nFS_LLM_BATCH_SIZE=3\n", encoding="utf-8"
    )
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--config",
            str(config),
            "--env-file",
            str(destination),
            "--model",
            model,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert config.read_text(encoding="utf-8") == original
    assert "fixture-private-key" not in result.stdout + result.stderr
    return result, dotenv_values(destination)


def test_import_uses_model_id_preserves_other_config_and_hides_secret(tmp_path):
    result, values = run_import(tmp_path)
    assert result.returncode == 0
    assert values["FS_LLM_MODEL"] == "volcengine/deepseek-v4.1-flash"
    assert values["FS_LLM_API_KEY"] == "fixture-private-key"
    assert values["FS_DATABASE_URL"] == "existing-database"
    assert values["FS_LLM_BATCH_SIZE"] == "3"


def test_unlisted_model_does_not_change_configuration(tmp_path):
    result, values = run_import(tmp_path, "unlisted-model")
    assert result.returncode != 0
    assert "FS_LLM_API_KEY" not in values and "FS_LLM_MODEL" not in values
