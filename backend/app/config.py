from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000"]

    # Database
    database_url: str
    database_url_sync: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Storage
    storage_endpoint: str = "http://localhost:9000"
    storage_access_key: str = "millipede"
    storage_secret_key: str = "millipede123"
    storage_bucket: str = "millipede"
    storage_region: str = "us-east-1"
    storage_use_ssl: bool = False

    # Auth
    secret_key: str
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # LLM — international
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    # LLM — China providers
    deepseek_api_key: str = ""
    volcengine_api_key: str = ""
    doubao_model_id: str = ""      # 火山方舟接入点 ID，形如 ep-xxxxxxxxx-xxxxx
    dashscope_api_key: str = ""

    default_llm_model: str = "deepseek/deepseek-chat"

    # Docker Sandbox
    sandbox_image: str = "millipede-sandbox:latest"
    sandbox_memory_limit: str = "2g"
    sandbox_cpu_limit: float = 1.0
    sandbox_network: str = "none"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v: str | list) -> list[str]:
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
