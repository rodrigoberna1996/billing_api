from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIASGIMiddleware
from starlette.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.database import dispose_engine, get_engine
from app.core.logging import configure_logging
from app.core.redis import close_redis, get_redis
from app.interfaces.api.exception_handlers import validation_exception_handler
from app.interfaces.api.internal_auth import require_internal_key
from app.interfaces.api.limiter import limiter
from app.interfaces.api.routers import (
    carta_porte,
    certificates,
    clients,
    drafts,
    facturify_empresa,
    health,
    mercancias,
)

logger = logging.getLogger(__name__)

_DEV_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
)


def _cors_origins(settings: Settings) -> list[str]:
    raw = settings.cors_allowed_origins.strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    if settings.env == "development":
        return list(_DEV_CORS_ORIGINS)
    return []


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    if settings.env == "production":
        if not settings.facturalo_api_key:
            raise RuntimeError(
                "FACTURALO_API_KEY no está configurada para producción. "
                "Revisa las variables de entorno."
            )
        if not settings.facturalo_emisor_rfc:
            # Ya no es obligatorio: el emisor se gestiona desde "Mi cuenta" en
            # adrh_logistics y se envía en cada request de timbrado. FACTURALO_EMISOR_*
            # queda solo como respaldo para llamadas que no incluyan `emisor`.
            logger.warning(
                "FACTURALO_EMISOR_RFC no está configurado; se usará únicamente el "
                "emisor recibido en cada request de timbrado (sin respaldo por entorno)."
            )
    get_engine()
    await get_redis()
    yield
    await close_redis()
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Billing API",
        description="Servicio de timbrado CFDI con complemento Carta Porte usando FacturaloPlus",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIASGIMiddleware)
    cors_origins = _cors_origins(settings)
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Error no manejado en %s", request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=500, content={"detail": "Error interno del servidor."}
        )

    app.include_router(health.router)

    internal_dep = [Depends(require_internal_key)]
    app.include_router(facturify_empresa.router, dependencies=internal_dep)
    app.include_router(carta_porte.router, dependencies=internal_dep)
    app.include_router(certificates.router, dependencies=internal_dep)
    app.include_router(clients.router, dependencies=internal_dep)
    app.include_router(drafts.router, dependencies=internal_dep)
    app.include_router(mercancias.router, dependencies=internal_dep)
    return app


app = create_app()
