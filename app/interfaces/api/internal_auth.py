"""Autenticacion interna mediante API Key para comunicacion servidor-a-servidor."""
import os
import logging

from fastapi import Header, HTTPException, status

logger = logging.getLogger(__name__)

_INTERNAL_KEY: str | None = os.getenv("INTERNAL_API_KEY")


async def require_internal_key(x_internal_key: str = Header(..., alias="X-Internal-Key")) -> None:
    """Dependencia que valida el header X-Internal-Key contra INTERNAL_API_KEY."""
    if not _INTERNAL_KEY:
        logger.error("INTERNAL_API_KEY no esta configurada en el entorno.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuracion de seguridad incompleta en el servidor.",
        )
    if x_internal_key != _INTERNAL_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key interna invalida o ausente.",
        )
