import os
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .topics import LEGACY_TOPICS

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FS_", env_file=PROJECT_ROOT / ".env", extra="ignore"
    )
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://frontiersignal@127.0.0.1:54329/frontiersignal"
    )
    scheduler_enabled: bool = True
    allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    extra_feed_hosts: list[str] = []
    outbound_proxy: SecretStr = Field(
        default_factory=lambda: SecretStr(
            os.environ.get("HTTPS_PROXY", os.environ.get("https_proxy", ""))
        )
    )
    fetch_timeout: int = Field(25, ge=2, le=120)
    task_timeout: int = Field(180, ge=10, le=600)
    collector_concurrency: int = Field(3, ge=1, le=8)
    max_items: int = Field(30, ge=1, le=100)
    citation_checks: int = Field(2, ge=0, le=5)
    llm_base_url: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""
    llm_timeout: int = Field(60, ge=5, le=180)
    llm_max_retries: int = Field(2, ge=0, le=5)
    llm_batch_size: int = Field(5, ge=1, le=30)
    llm_json_mode: bool = False
    prefilter_keywords: list[str] = []
    embedding_model: str = ""
    semantic_threshold: float = Field(0.94, ge=0.8, le=1)
    github_token: SecretStr = SecretStr("")
    github_queries_per_run: int = Field(2, ge=1, le=4)
    github_candidates_per_query: int = Field(10, ge=1, le=30)
    github_track_per_run: int = Field(10, ge=1, le=15)
    github_code_checks: int = Field(3, ge=0, le=10)
    github_readme_checks: int = Field(2, ge=0, le=5)
    github_history_checks: int = Field(8, ge=0, le=15)
    hf_queries_per_run: int = Field(6, ge=1, le=6)
    hf_candidates_per_query: int = Field(5, ge=1, le=10)
    hf_card_checks: int = Field(6, ge=0, le=15)
    hn_candidates: int = Field(60, ge=10, le=150)
    hn_comment_limit: int = Field(3, ge=0, le=10)
    interest_topics: list[str] = Field(default_factory=lambda: list(LEGACY_TOPICS))

    @field_validator("llm_base_url")
    @classmethod
    def validate_llm_url(cls, value):
        if not value:
            return value
        parsed = urlsplit(value)
        local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if (
            not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or (parsed.scheme != "https" and not (local and parsed.scheme == "http"))
        ):
            raise ValueError(
                "LLM URL must be HTTPS or explicit loopback HTTP without embedded secrets"
            )
        return value.rstrip("/")

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_model and self.llm_api_key.get_secret_value())


settings = Settings()
