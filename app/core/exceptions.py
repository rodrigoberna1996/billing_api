"""Excepciones de dominio controladas."""
from __future__ import annotations


class BillingError(RuntimeError):
    """Raiz de errores de dominio/control."""


class EntityNotFound(BillingError):
    """Entidad no localizada en repositorios."""


class ExternalServiceError(BillingError):
    """Errores provenientes de integraciones externas."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        source: str = "facturaloplus",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.source = source


class ValidationError(BillingError):
    """Errores de negocio que deben ser devueltos al cliente."""
