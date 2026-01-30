"""Exception handlers personalizados para FastAPI."""
from __future__ import annotations

import json
import logging

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handler personalizado para errores de validación de Pydantic."""
    logger.error("=" * 100)
    logger.error("❌ ERROR DE VALIDACIÓN DE PYDANTIC")
    logger.error(f"🔗 URL: {request.method} {request.url.path}")
    logger.error(f"📋 Content-Type: {request.headers.get('content-type', 'NOT SET')}")
    
    try:
        body = await request.body()
        logger.error(f"📏 Content-Length: {len(body)} bytes")
        logger.error("📦 RAW BODY recibido:")
        logger.error(body.decode('utf-8', errors='replace'))
        
        try:
            parsed = json.loads(body)
            logger.error(f"✅ Body se puede parsear como JSON: {type(parsed)}")
            if isinstance(parsed, dict):
                logger.error(f"🔑 Keys encontradas: {list(parsed.keys())}")
        except json.JSONDecodeError:
            logger.error("❌ Body NO es JSON válido")
    except Exception as e:
        logger.error(f"❌ Error al leer body: {e}")
    
    logger.error("🚨 ERRORES DE VALIDACIÓN:")
    for error in exc.errors():
        logger.error(f"  - Tipo: {error.get('type')}")
        logger.error(f"    Ubicación: {error.get('loc')}")
        logger.error(f"    Mensaje: {error.get('msg')}")
        input_value = error.get('input', 'N/A')
        input_str = str(input_value)[:200] if input_value != 'N/A' else 'N/A'
        logger.error(f"    Input: {input_str}")
    
    logger.error("=" * 100)
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "body": exc.body,
        },
    )
