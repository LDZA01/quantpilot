from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://quantpilot:quantpilot@localhost:5432/quantpilot"
    cors_origin: str = "http://localhost:3000"
    ingestion_attempts: int = Field(default=3, ge=1, le=5)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator("database_url")
    @classmethod
    def database_scheme(cls, value: str) -> str:
        if not value.startswith(("postgresql+psycopg://", "sqlite://")):
            raise ValueError("Use a PostgreSQL psycopg URL or the SQLite test adapter")
        return value

    @field_validator("cors_origin")
    @classmethod
    def origin(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path:
            raise ValueError("CORS origin must be an HTTP(S) origin without a path")
        return value


@lru_cache
def settings() -> Settings:
    return Settings()
