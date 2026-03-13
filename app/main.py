from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, ORJSONResponse

from app.core.config import get_settings
from app.core.database import dispose_engine, get_engine
from app.core.logging import configure_logging
from app.core.redis import close_redis, get_redis
from app.infrastructure.http.facturify_auth_client import (
    close_facturify_auth_client,
    get_facturify_auth_client,
)
from app.infrastructure.http.facturify_empresa_client import close_facturify_empresa_client
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIASGIMiddleware

from app.interfaces.api.exception_handlers import validation_exception_handler
from app.interfaces.api.internal_auth import require_internal_key
from app.interfaces.api.limiter import limiter
from app.interfaces.api.routers import carta_porte, clients, facturify_auth, facturify_empresa, health

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    settings = get_settings()
    # Validacion de credenciales criticas antes de arrancar en produccion
    if settings.env == "production":
        if settings.facturify_api_key == "demo-token":
            raise RuntimeError(
                "FACTURIFY_API_KEY no esta configurada para produccion. "
                "Revisa las variables de entorno."
            )
        if settings.facturify_account_uuid == "00000000-0000-0000-0000-000000000000":
            raise RuntimeError(
                "FACTURIFY_ACCOUNT_UUID no esta configurado para produccion. "
                "Revisa las variables de entorno."
            )
    get_engine()
    await get_redis()
    auth_client = await get_facturify_auth_client()
    await auth_client.start_background_refresh()
    yield
    await close_facturify_empresa_client()
    await close_facturify_auth_client()
    await close_redis()
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Billing API",
        description="Servicio de timbrado CFDI con complemento Carta Porte usando Facturify",
        version="0.1.0",
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIASGIMiddleware)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Error no manejado en %s", request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=500, content={"detail": "Error interno del servidor."}
        )

    # El router de health no requiere autenticacion para monitoreo de infra
    app.include_router(health.router)

    # Todos los demas routers requieren X-Internal-Key
    internal_dep = [Depends(require_internal_key)]
    app.include_router(facturify_auth.router, dependencies=internal_dep)
    app.include_router(facturify_empresa.router, dependencies=internal_dep)
    app.include_router(carta_porte.router, dependencies=internal_dep)
    app.include_router(clients.router, dependencies=internal_dep)
    return app


app = create_app()
