"""Borradores de formulario de factura en Redis (autoguardado server-side)."""

import json
import logging
from uuid import UUID, uuid4

import orjson
from fastapi import APIRouter, HTTPException, Request, status
from redis.exceptions import RedisError

from app.application.dtos import (
    DraftCreateBody,
    DraftCreatedResponse,
    DraftGetResponse,
    DraftUpsertBody,
)
from app.core.config import get_settings
from app.core.redis import delete_key, get_ttl, get_value, set_with_expiry
from app.interfaces.api.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["drafts"])

_DRAFT_KEY_PREFIX = "billing:invoice_draft:"


def _redis_key(draft_id: UUID) -> str:
    return f"{_DRAFT_KEY_PREFIX}{draft_id}"


def _serialize_payload(payload: dict) -> str:
    raw = orjson.dumps(payload)
    max_bytes = get_settings().invoice_draft_max_bytes
    if len(raw) > max_bytes:
        msg = f"El borrador excede el tamano maximo permitido ({max_bytes} bytes)."
        raise ValueError(msg)
    return raw.decode("utf-8")


async def _create_draft(create: DraftCreateBody) -> DraftCreatedResponse:
    settings = get_settings()
    draft_id = uuid4()
    payload = create.payload
    try:
        serialized = _serialize_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    try:
        await set_with_expiry(_redis_key(draft_id), serialized, settings.invoice_draft_ttl_seconds)
    except RedisError as exc:
        logger.exception("Redis no disponible al crear borrador")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo guardar el borrador (servicio temporalmente no disponible).",
        ) from exc
    return DraftCreatedResponse(draft_id=draft_id, expires_in_seconds=settings.invoice_draft_ttl_seconds)


@router.post(
    "/drafts",
    response_model=DraftCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("30/minute")
async def create_draft_endpoint(
    request: Request,
    create: DraftCreateBody,
) -> DraftCreatedResponse:
    return await _create_draft(create)


@router.post(
    "/drafts/",
    response_model=DraftCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
@limiter.limit("30/minute")
async def create_draft_endpoint_trailing_slash(
    request: Request,
    create: DraftCreateBody,
) -> DraftCreatedResponse:
    return await _create_draft(create)


@router.put("/drafts/{draft_id}", response_model=DraftGetResponse)
@limiter.limit("120/minute")
async def save_draft_endpoint(
    request: Request,
    draft_id: UUID,
    upsert: DraftUpsertBody,
) -> DraftGetResponse:
    settings = get_settings()
    key = _redis_key(draft_id)
    try:
        serialized = _serialize_payload(upsert.payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    try:
        await set_with_expiry(key, serialized, settings.invoice_draft_ttl_seconds)
    except RedisError as exc:
        logger.exception("Redis no disponible al guardar borrador %s", draft_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo guardar el borrador (servicio temporalmente no disponible).",
        ) from exc
    try:
        ttl = await get_ttl(key)
    except RedisError as exc:
        logger.exception("Redis no disponible al leer TTL borrador %s", draft_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo guardar el borrador (servicio temporalmente no disponible).",
        ) from exc
    expires = ttl if ttl > 0 else settings.invoice_draft_ttl_seconds
    return DraftGetResponse(payload=upsert.payload, expires_in_seconds=expires)


@router.get("/drafts/{draft_id}", response_model=DraftGetResponse)
@limiter.limit("120/minute")
async def get_draft_endpoint(request: Request, draft_id: UUID) -> DraftGetResponse:
    settings = get_settings()
    key = _redis_key(draft_id)
    try:
        raw = await get_value(key)
    except RedisError as exc:
        logger.exception("Redis no disponible al leer borrador %s", draft_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo leer el borrador (servicio temporalmente no disponible).",
        ) from exc
    if raw is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Borrador no encontrado o expirado.")
    try:
        payload = orjson.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Borrador corrupto en Redis: %s", draft_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Borrador almacenado invalido.",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Formato de borrador invalido.",
        )
    try:
        ttl = await get_ttl(key)
    except RedisError as exc:
        logger.exception("Redis no disponible al leer TTL borrador %s", draft_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo leer el borrador (servicio temporalmente no disponible).",
        ) from exc
    expires = ttl if ttl > 0 else settings.invoice_draft_ttl_seconds
    return DraftGetResponse(payload=payload, expires_in_seconds=expires)


@router.delete("/drafts/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def delete_draft_endpoint(request: Request, draft_id: UUID) -> None:
    try:
        await delete_key(_redis_key(draft_id))
    except RedisError as exc:
        logger.exception("Redis no disponible al eliminar borrador %s", draft_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo eliminar el borrador (servicio temporalmente no disponible).",
        ) from exc
