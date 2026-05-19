from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_env: str = "development"
    app_secret_key: str = "change-me"
    debug: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://trading:trading_secret@localhost:5432/trading_mvp"
    duckdb_path: str = "./trading_data.duckdb"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Vector DB
    chroma_host: str = "localhost"
    chroma_port: int = 8001

    # AI / LLM
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Market Data
    news_api_key: str = ""
    fred_api_key: str = ""
    polygon_api_key: str = ""
    tradier_api_key: str = ""
    fmp_api_key: str = ""
    unusual_whales_api_key: str = ""

    # Social
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "trading-engine-mvp/1.0"
    stocktwits_api_key: str = ""

    # Auth
    jwt_secret_key: str = "change-me-jwt"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # CORS
    allowed_origins: str = "http://localhost:3000"

    # Monitoring
    sentry_dsn: str = ""

    # Scheduler
    scheduler_timezone: str = "Asia/Kolkata"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
