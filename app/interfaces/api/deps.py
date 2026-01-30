"""Dependencias para FastAPI."""
from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends

from app.application.services.create_carta_porte import CreateCartaPorteService, UnitOfWorkFactory
from app.core.config import Settings, get_settings
from app.core.database import get_session_factory
from app.infrastructure.http.facturify_client import FacturifyClient
from app.infrastructure.mappers.facturify_payload import FacturifyPayloadBuilder
from app.infrastructure.persistence.unit_of_work import SQLAlchemyUnitOfWork


def get_app_settings() -> Settings:
    return get_settings()


def get_uow_factory() -> UnitOfWorkFactory:
    session_factory = get_session_factory()

    def factory() -> SQLAlchemyUnitOfWork:
        return SQLAlchemyUnitOfWork(session_factory)

    return factory


def get_facturify_client(settings: Settings = Depends(get_app_settings)) -> FacturifyClient:
    return FacturifyClient(
        base_url=settings.facturify_base_url,
        timeout=settings.facturify_timeout,
        max_retries=settings.facturify_max_retries,
        retry_backoff=settings.facturify_retry_backoff,
    )


def get_payload_builder(settings: Settings = Depends(get_app_settings)) -> FacturifyPayloadBuilder:
    return FacturifyPayloadBuilder(account_uuid=settings.facturify_account_uuid)


def get_create_carta_porte_service(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    facturify_client: FacturifyClient = Depends(get_facturify_client),
    payload_builder: FacturifyPayloadBuilder = Depends(get_payload_builder),
) -> CreateCartaPorteService:
    return CreateCartaPorteService(uow_factory, facturify_client, payload_builder)
