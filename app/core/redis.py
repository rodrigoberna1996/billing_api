"""Redis client configuration and management."""
from __future__ import annotations

import logging
from typing import Any

from redis.asyncio import Redis, from_url

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_redis_client: Redis | None = None


async def get_redis() -> Redis:
    """Get or create Redis client instance."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = from_url(
            settings.redis_url,
            decode_responses=settings.redis_decode_responses,
            encoding="utf-8",
        )
        logger.info("Redis client initialized")
    return _redis_client


async def close_redis() -> None:
    """Close Redis connection."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis client closed")


async def set_with_expiry(key: str, value: str, expiry_seconds: int) -> None:
    """Set a key with expiry time in Redis."""
    redis = await get_redis()
    await redis.setex(key, expiry_seconds, value)


async def get_value(key: str) -> str | None:
    """Get a value from Redis."""
    redis = await get_redis()
    return await redis.get(key)


async def delete_key(key: str) -> None:
    """Delete a key from Redis."""
    redis = await get_redis()
    await redis.delete(key)


async def get_ttl(key: str) -> int:
    """Get TTL (time to live) of a key in seconds. Returns -2 if key doesn't exist, -1 if no expiry."""
    redis = await get_redis()
    return await redis.ttl(key)
