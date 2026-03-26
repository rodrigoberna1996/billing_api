"""Autenticacion interna mediante API Key para comunicacion servidor-a-servidor."""
import logging

from fastapi import Header, HTTPException, status

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def require_internal_key(x_internal_key: str = Header(..., alias="X-Internal-Key")) -> None:
    """Dependencia que valida el header X-Internal-Key contra INTERNAL_API_KEY."""
    internal_key = get_settings().internal_api_key
    if not internal_key:
        logger.error("INTERNAL_API_KEY no esta configurada en el entorno.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuracion de seguridad incompleta en el servidor.",
        )
    if x_internal_key != internal_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key interna invalida o ausente.",
        )
