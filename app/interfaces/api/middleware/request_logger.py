"""Middleware para loggear requests raw antes de que FastAPI los procese."""
from __future__ import annotations

import json
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """Middleware que loggea el body raw de cada request."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Intercepta el request, loggea el body y continúa."""
        if request.method in ("POST", "PUT", "PATCH"):
            body = await request.body()
            
            logger.info("=" * 100)
            logger.info(f"🔍 RAW REQUEST - {request.method} {request.url.path}")
            logger.info(f"📋 Content-Type: {request.headers.get('content-type', 'NOT SET')}")
            logger.info(f"📏 Content-Length: {len(body)} bytes")
            logger.info("📦 RAW BODY (primeros 2000 chars):")
            logger.info(body[:2000].decode('utf-8', errors='replace'))
            
            try:
                parsed = json.loads(body)
                logger.info("✅ JSON PARSEADO CORRECTAMENTE")
                logger.info(f"🔑 Tipo del objeto parseado: {type(parsed)}")
                logger.info(f"🔑 Keys del objeto: {list(parsed.keys()) if isinstance(parsed, dict) else 'NO ES DICT'}")
            except json.JSONDecodeError as e:
                logger.error(f"❌ ERROR AL PARSEAR JSON: {e}")
            except Exception as e:
                logger.error(f"❌ ERROR INESPERADO: {e}")
            
            logger.info("=" * 100)
            
            async def receive():
                return {"type": "http.request", "body": body}
            
            request._receive = receive
        
        response = await call_next(request)
        return response
