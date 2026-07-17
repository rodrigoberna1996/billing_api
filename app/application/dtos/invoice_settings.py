"""DTOs de configuración de serie/folio de facturación (módulo 'Mi cuenta')."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class InvoiceSettingsRead(BaseModel):
    serie: str
    next_folio: int
    updated_at: datetime | None = None


class InvoiceSettingsUpdate(BaseModel):
    serie: str = Field(..., min_length=1, max_length=10)
    next_folio: int = Field(..., ge=1)

    @field_validator("serie")
    @classmethod
    def _normalize_serie(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            msg = "La serie no puede estar vacía"
            raise ValueError(msg)
        return normalized
