from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse

from app.core.config import get_settings
from app.core.database import dispose_engine, get_engine
from app.core.logging import configure_logging
from app.core.redis import close_redis, get_redis
from app.infrastructure.http.facturify_auth_client import (
    close_facturify_auth_client,
    get_facturify_auth_client,
)
from app.infrastructure.http.facturify_empresa_client import close_facturify_empresa_client
from app.interfaces.api.exception_handlers import validation_exception_handler
from app.interfaces.api.middleware import RequestLoggerMiddleware
from app.interfaces.api.routers import carta_porte, clients, facturify_auth, facturify_empresa, health


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
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

    app.add_middleware(RequestLoggerMiddleware)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    app.include_router(health.router)
    app.include_router(facturify_auth.router)
    app.include_router(facturify_empresa.router)
    app.include_router(carta_porte.router)
    app.include_router(clients.router)
    return app


app = create_app()
