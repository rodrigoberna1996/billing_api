"""Excepciones de dominio controladas."""
from __future__ import annotations


class BillingError(RuntimeError):
    """Raiz de errores de dominio/control."""


class EntityNotFound(BillingError):
    """Entidad no localizada en repositorios."""


class ExternalServiceError(BillingError):
    """Errores provenientes de integraciones externas."""


class ValidationError(BillingError):
    """Errores de negocio que deben ser devueltos al cliente."""
