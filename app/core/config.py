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

    invoice_draft_ttl_seconds: int = Field(default=2592000, alias="INVOICE_DRAFT_TTL_SECONDS")
    invoice_draft_max_bytes: int = Field(default=524288, alias="INVOICE_DRAFT_MAX_BYTES")

    # FacturaloPlus PAC
    facturalo_base_url: str = Field(default="https://dev.facturaloplus.com", alias="FACTURALO_BASE_URL")
    facturalo_api_key: str = Field(default="", alias="FACTURALO_API_KEY")
    facturalo_key_pem: str = Field(default="", alias="FACTURALO_KEY_PEM")
    facturalo_cer_pem: str = Field(default="", alias="FACTURALO_CER_PEM")
    facturalo_csd_key_b64: str = Field(default="", alias="FACTURALO_CSD_KEY_B64")
    facturalo_csd_cer_b64: str = Field(default="", alias="FACTURALO_CSD_CER_B64")
    facturalo_csd_password: str = Field(default="", alias="FACTURALO_CSD_PASSWORD")
    facturalo_csd_serial: str = Field(default="", alias="FACTURALO_CSD_SERIAL")
    facturalo_timeout: int = Field(default=30, alias="FACTURALO_TIMEOUT")
    facturalo_max_retries: int = Field(default=3, alias="FACTURALO_MAX_RETRIES")
    facturalo_retry_backoff: float = Field(default=2.0, alias="FACTURALO_RETRY_BACKOFF")

    # Emisor (empresa timbradora) configurado en .env
    facturalo_emisor_rfc: str = Field(default="", alias="FACTURALO_EMISOR_RFC")
    facturalo_emisor_nombre: str = Field(default="", alias="FACTURALO_EMISOR_NOMBRE")
    facturalo_emisor_regimen: str = Field(default="601", alias="FACTURALO_EMISOR_REGIMEN")
    facturalo_emisor_cp: str = Field(default="", alias="FACTURALO_EMISOR_CP")
    facturalo_pdf_plantilla: str = Field(
        default="transporteterrestre31",
        alias="FACTURALO_PDF_PLANTILLA",
    )
    # Ruta al logo PNG/JPEG del emisor para el PDF (relativa a la raíz del repo o absoluta)
    facturalo_logo_path: str = Field(
        default="assets/logo_transportes_ruiz.png",
        alias="FACTURALO_LOGO_PATH",
    )

    # Integración con adrh_logistics (callback event-driven post-timbrado)
    logistics_api_url: str = Field(default="", alias="LOGISTICS_API_URL")
    logistics_api_key: str = Field(default="", alias="LOGISTICS_API_KEY")

    internal_api_key: str | None = Field(default=None, alias="INTERNAL_API_KEY")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    cors_allowed_origins: str = Field(
        default="",
        alias="CORS_ALLOWED_ORIGINS",
    )

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings(**overrides: Any) -> Settings:
    """Permite cachear la configuracion y facilitar su sobreescritura en tests."""
    return Settings(**overrides)
