"""Endpoint de empresa/emisor — devuelve el emisor configurado en .env (sin llamar Facturify)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.core.config import Settings
from app.interfaces.api.deps import get_app_settings
from app.interfaces.api.schemas.facturify_empresa import (
    Empresa,
    EmpresaListResponse,
    EmpresaResponse,
    Meta,
    Pagination,
)

router = APIRouter(prefix="/api/v1/facturify/empresa", tags=["Empresa"])


def _emisor_from_settings(settings: Settings) -> Empresa:
    return Empresa(
        uuid=str(uuid.uuid5(uuid.NAMESPACE_DNS, settings.facturalo_emisor_rfc or "default")),
        tipo="moral",
        razon_social=settings.facturalo_emisor_nombre,
        organizacion_uuid="",
        rfc=settings.facturalo_emisor_rfc,
        regimen=settings.facturalo_emisor_regimen,
        cp=settings.facturalo_emisor_cp,
        calle="",
        colonia="",
        delegacion_municipio="",
        estado="",
        curp="",
        inscrito_en_terceros=0,
        factura_por_cuenta_de_terceros=0,
        status="active",
        razon_status="Activo",
    )


@router.get(
    "/",
    response_model=EmpresaListResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtiene el emisor configurado",
    description="Retorna el emisor (empresa) configurado vía variables de entorno FACTURALO_EMISOR_*.",
)
async def get_empresas(
    settings: Settings = Depends(get_app_settings),
) -> EmpresaListResponse:
    empresa = _emisor_from_settings(settings)
    return EmpresaListResponse(
        data=[empresa],
        meta=Meta(
            pagination=Pagination(total=1, count=1, per_page=10, current_page=1, total_pages=1)
        ),
    )


@router.get(
    "/rfc/{rfc}",
    response_model=EmpresaResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtiene empresa por RFC",
    description="Retorna el emisor si el RFC coincide con el configurado.",
)
async def get_empresa_by_rfc(
    rfc: str,
    settings: Settings = Depends(get_app_settings),
) -> EmpresaResponse:
    empresa = _emisor_from_settings(settings)
    return EmpresaResponse(data=empresa)
