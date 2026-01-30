"""DTOs para respuestas de error estructuradas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Detalle estructurado de un error."""

    error_code: str = Field(default="", description="Código de error del SAT o PAC")
    pac: str = Field(default="", description="Proveedor de certificación (Finkok, etc)")
    message: str = Field(..., description="Mensaje de error para el usuario")
    sat_message: str | None = Field(default=None, description="Mensaje original del SAT")
    original_message: str | None = Field(default=None, description="Mensaje original completo")


class ErrorResponse(BaseModel):
    """Respuesta de error de la API."""

    success: bool = Field(default=False)
    detail: str = Field(..., description="Mensaje de error principal")
    error: ErrorDetail | None = Field(default=None, description="Detalles adicionales del error")
