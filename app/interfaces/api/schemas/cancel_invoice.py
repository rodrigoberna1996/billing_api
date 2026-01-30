"""Schemas for invoice cancellation endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CancelInvoiceResponse(BaseModel):
    """Response for successful invoice cancellation."""
    message: str


class CancelErrorDetail(BaseModel):
    """Error detail for cancellation."""
    field: str
    message: str
    code: int


class CancelErrorResponse(BaseModel):
    """Error response for cancellation."""
    code: int
    message: str
    errors: list[CancelErrorDetail] = Field(default_factory=list)
