"""Runtime configuration from environment variables (and .env for local development)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Trading Engine"
    environment: str = "development"

    # LLM providers. The server key for DEFAULT_LLM_PROVIDER is shared by every visitor who has not set
    # their own key, so it is rate limited (see llm_shared_* below). Visitors may bring their own key for
    # any provider in Settings; those calls are not counted against the shared budget.
    default_llm_provider: str = "groq"          # groq | gemini | anthropic
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"
    llm_timeout_s: float = 40.0

    # Shared-key budgets (per serverless instance)
    llm_shared_per_minute: int = 5
    llm_shared_per_day: int = 600
    llm_shared_per_ip_10min: int = 8

    # Compute budgets for model training endpoints (per client IP, per instance)
    train_per_ip_10min: int = 40

    # CORS: only needed when the API is called from another origin (the bundled UI is same-origin)
    allowed_origins: str = "*"

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
