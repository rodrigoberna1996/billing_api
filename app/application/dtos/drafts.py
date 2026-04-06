"""DTOs para borradores de formulario (almacenados en Redis)."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DraftCreateBody(BaseModel):
    """Cuerpo opcional al crear un borrador vacio o con datos iniciales."""

    payload: dict[str, Any] = Field(default_factory=dict)


class DraftUpsertBody(BaseModel):
    """Sustituye el JSON completo del borrador (autoguardado del frontend)."""

    payload: dict[str, Any]


class DraftCreatedResponse(BaseModel):
    draft_id: UUID
    expires_in_seconds: int


class DraftGetResponse(BaseModel):
    payload: dict[str, Any]
    expires_in_seconds: int
