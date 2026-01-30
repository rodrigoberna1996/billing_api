"""Schemas for Facturify authentication endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field


class JWTResponse(BaseModel):
    """JWT token response."""
    token: str
    expires_in: int


class AuthResponse(BaseModel):
    """Authentication response."""
    message: str
    jwt: JWTResponse


class TokenStatusResponse(BaseModel):
    """Token status response."""
    has_token: bool
    ttl: int | None = Field(None, description="Time to live in seconds, None if no token")
    expires_in: int | None = Field(None, description="Original expiry time if available")


class ErrorDetail(BaseModel):
    """Error detail."""
    field: str
    message: str
    code: int


class ValidationErrorResponse(BaseModel):
    """Validation error response."""
    code: int
    message: str
    errors: list[ErrorDetail]


class UnauthorizedErrorResponse(BaseModel):
    """Unauthorized error response."""
    message: str
    code: int | None = None
