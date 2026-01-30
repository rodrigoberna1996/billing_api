"""Schemas for Facturify empresa (company) endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Pagination(BaseModel):
    """Pagination details."""
    total: int
    count: int
    per_page: int
    current_page: int
    total_pages: int
    links: list = []


class Meta(BaseModel):
    """Response metadata."""
    pagination: Pagination


class Empresa(BaseModel):
    """Empresa registrada en Facturify."""
    uuid: str
    tipo: str
    razon_social: str
    organizacion_uuid: str
    rfc: str
    regimen: str
    email: str | None = None
    cp: str
    calle: str | None = None
    num_ext: str | None = None
    num_int: str | None = None
    colonia: str
    delegacion_municipio: str
    ciudad: str | None = None
    estado: str
    curp: str
    inscrito_en_terceros: int
    factura_por_cuenta_de_terceros: int
    facturacion_por_terceros_habilitado: int | None = None
    schema: str | None = None
    status: str
    direccion_fiscal_pdf: bool | None = None
    razon_status: str
    folios_timbrado: str | None = None
    tipo_pago: str | None = None
    fecha_alta_sat: str | None = None
    path_pdf_constancia: str | None = None
    status_constancia: int | None = None
    last_revision: str | None = None
    registro_patronal: str | None = None
    guardar_fiel: bool | None = None
    origen_recurso_tipo: str | None = None
    monto_recurso_propio: str | None = None
    ciudad_id: str | None = None
    org_uuid: str | None = None
    org_tipo: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class EmpresaListResponse(BaseModel):
    """Response for empresa list endpoint."""
    data: list[Empresa]
    meta: Meta


class EmpresaResponse(BaseModel):
    """Response for single empresa."""
    data: Empresa
