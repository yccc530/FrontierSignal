"""Create private local configuration without overwriting existing settings."""

import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".env"
if target.exists():
    print("Existing .env preserved.")
else:
    password = secrets.token_urlsafe(32)
    value = (root / ".env.example").read_text(encoding="utf-8").replace("CHANGE_ME", password)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as file:
        file.write(value)
    print("Created .env with a random database password. No LLM credentials configured.")
