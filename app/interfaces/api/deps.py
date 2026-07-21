"""Dependencias para FastAPI."""
from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends

from app.application.ports.repositories import UnitOfWork
from app.core.config import Settings, get_settings
from app.core.database import get_session_factory
from app.infrastructure.http.facturalo_client import FacturaloPlusClient
from app.infrastructure.http.logistics_client import LogisticsClient
from app.infrastructure.mappers.facturalo_payload import FacturaloPayloadBuilder
from app.infrastructure.persistence.unit_of_work import SQLAlchemyUnitOfWork

UnitOfWorkFactory = Callable[[], UnitOfWork]


def get_app_settings() -> Settings:
    return get_settings()


def get_uow_factory() -> UnitOfWorkFactory:
    session_factory = get_session_factory()

    def factory() -> SQLAlchemyUnitOfWork:
        return SQLAlchemyUnitOfWork(session_factory)

    return factory


def get_facturalo_client(settings: Settings = Depends(get_app_settings)) -> FacturaloPlusClient:
    return FacturaloPlusClient(
        base_url=settings.facturalo_base_url,
        api_key=settings.facturalo_api_key,
        key_pem=settings.facturalo_key_pem,
        cer_pem=settings.facturalo_cer_pem,
        csd_key_b64=settings.facturalo_csd_key_b64,
        csd_cer_b64=settings.facturalo_csd_cer_b64,
        csd_password=settings.facturalo_csd_password,
        emisor_rfc=settings.facturalo_emisor_rfc,
        pdf_plantilla=settings.facturalo_pdf_plantilla,
        timeout=settings.facturalo_timeout,
        max_retries=settings.facturalo_max_retries,
        retry_backoff=settings.facturalo_retry_backoff,
    )


def get_facturalo_payload_builder(settings: Settings = Depends(get_app_settings)) -> FacturaloPayloadBuilder:
    return FacturaloPayloadBuilder(
        emisor_rfc=settings.facturalo_emisor_rfc,
        emisor_nombre=settings.facturalo_emisor_nombre,
        emisor_regimen=settings.facturalo_emisor_regimen,
        emisor_cp=settings.facturalo_emisor_cp,
        csd_serial=settings.facturalo_csd_serial,
        logo_path=settings.facturalo_logo_path,
    )


def get_logistics_client(settings: Settings = Depends(get_app_settings)) -> LogisticsClient:
    return LogisticsClient(
        base_url=settings.logistics_api_url,
        api_key=settings.logistics_api_key,
    )
