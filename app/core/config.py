"""Configuracion de la aplicacion."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Carga tipada de variables de entorno."""

    env: str = Field(default="development", alias="BILLING_API_ENV")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    database_url: str = Field(
        default="postgresql+asyncpg://billing_api:billing_api@localhost:5432/billing_api",
        alias="DATABASE_URL",
    )
    db_echo: bool = Field(default=False, alias="DB_ECHO")

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_decode_responses: bool = Field(default=True, alias="REDIS_DECODE_RESPONSES")

    facturify_base_url: str = Field(default="https://api-sandbox.facturify.com", alias="FACTURIFY_BASE_URL")
    facturify_api_key: str = Field(default="demo-token", alias="FACTURIFY_API_KEY")
    facturify_api_secret: str = Field(default="demo-secret", alias="FACTURIFY_API_SECRET")
    facturify_account_uuid: str = Field(
        default="00000000-0000-0000-0000-000000000000", alias="FACTURIFY_ACCOUNT_UUID"
    )
    facturify_timeout: int = Field(default=30, alias="FACTURIFY_TIMEOUT")
    facturify_max_retries: int = Field(default=3, alias="FACTURIFY_MAX_RETRIES")
    facturify_retry_backoff: float = Field(default=2.0, alias="FACTURIFY_RETRY_BACKOFF")
    facturify_token_refresh_buffer: int = Field(default=60, alias="FACTURIFY_TOKEN_REFRESH_BUFFER")

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings(**overrides: Any) -> Settings:
    """Permite cachear la configuracion y facilitar su sobreescritura en tests."""

    return Settings(**overrides)
