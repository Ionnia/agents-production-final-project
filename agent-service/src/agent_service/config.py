from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Contract A — token the backend presents to us.
    agent_service_token: str = "dev-agent-service-token"

    # Contract B — how we reach the backend's /internal/* and the token we present.
    backend_base_url: str = "http://localhost:8000"
    backend_tool_token: str = "dev-backend-tool-token"
    backend_connect_timeout_seconds: float = 5.0
    backend_read_timeout_seconds: float = 30.0

    # GigaChat for the Final agent runtime.
    gigachat_credentials: str = ""
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_model: str = "GigaChat-2-Max"

    host: str = "0.0.0.0"
    port: int = 8001
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
