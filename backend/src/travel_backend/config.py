from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    access_token_ttl_minutes: int
    refresh_token_ttl_days: int
    backend_tool_token: str
    agent_service_url: str
    agent_service_token: str
    default_locale: str
    supported_locales: Annotated[list[str], NoDecode]
    cors_origins: Annotated[list[str], NoDecode]
    log_level: str
    agent_connect_timeout_seconds: float = 5.0
    agent_read_timeout_seconds: float = 120.0
    stream_ticket_ttl_seconds: int = 60
    stream_reconnect_lease_seconds: int = 300
    sse_poll_interval_seconds: float = 0.25
    data_dir: Path = Path(__file__).resolve().parents[3] / "data"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("supported_locales", "cors_origins", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
