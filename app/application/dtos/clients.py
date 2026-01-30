"""DTOs para el manejo de clientes desde Facturify."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ClientDTO(BaseModel):
    uuid: str
    alias: str | None = None
    facturacion: str | None = None
    razon_social: str
    rfc: str
    email: str | None = None
    tarjeta_ultimos_4digitos: str | None = None
    metodo_de_pago: str | None = None
    forma_de_pago: str | None = None
    uso_cfdi: str | None = None
    empresa_uuid: str | None = None
    organizacion_uuid: str | None = None
    calle: str | None = None
    num_ext: str | None = None
    num_int: str | None = None
    colonia: str | None = None
    delegacion_municipio: str | None = None
    cp: str | None = None
    estado: str | None = None
    ciudad: str | None = None
    telefono_fijo: str | None = None
    celular: str | None = None
    activo: int | None = None
    representante_legal: str | None = None
    marca_representada: str | None = None
    linea_de_negocio: str | None = None
    pais: str | None = None
    region: str | None = None
    city: str | None = None
    centro_de_atencion: str | None = None
    direccion_fiscal_pdf: bool | None = None
    email_pdf: bool | None = None
    nom_den_raz_soc_r: str | None = None
    nacionalidad: str | None = None
    num_reg_id_trib: str | None = None
    consolidated_begin_date: str | None = None
    consolidated_end_date: str | None = None
    consolidated_org_name: str | None = None
    consolidated_org_uuid: str | None = None
    consolidated: bool | None = None
    consolidated_org: bool | None = None
    regimen: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    class Config:
        extra = "allow"


class PaginationLinks(BaseModel):
    next: str | None = None
    previous: str | None = None

    class Config:
        extra = "allow"


class PaginationInfo(BaseModel):
    total: int
    count: int
    per_page: int
    current_page: int
    total_pages: int
    links: PaginationLinks | dict | list = Field(default_factory=dict)

    class Config:
        extra = "allow"


class MetaInfo(BaseModel):
    pagination: PaginationInfo

    class Config:
        extra = "allow"


class ClientsListResponse(BaseModel):
    data: list[ClientDTO]
    meta: MetaInfo

    class Config:
        extra = "allow"


class ErrorDetail(BaseModel):
    field: str
    message: str
    code: int


class ErrorResponse(BaseModel):
    code: int
    message: str
    errors: list[ErrorDetail] | None = None
