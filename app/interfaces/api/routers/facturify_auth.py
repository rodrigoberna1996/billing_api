"""API endpoints for Facturify authentication management."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.core.redis import get_ttl, get_value
from app.infrastructure.http.facturify_auth_client import (
    FacturifyAuthError,
    get_facturify_auth_client,
)
from app.interfaces.api.schemas.facturify_auth import (
    AuthResponse,
    TokenStatusResponse,
    UnauthorizedErrorResponse,
    ValidationErrorResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/facturify/auth", tags=["Facturify Authentication"])


@router.post(
    "/token",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": UnauthorizedErrorResponse},
        422: {"model": ValidationErrorResponse},
    },
    summary="Obtain Facturify authentication token",
    description="Obtains a new authentication token from Facturify API and stores it in cache.",
)
async def obtain_token() -> AuthResponse:
    """Obtain a new authentication token from Facturify."""
    try:
        client = await get_facturify_auth_client()
        result = await client.obtain_token()
        return AuthResponse(**result)
    except FacturifyAuthError as e:
        logger.error(f"Failed to obtain token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error obtaining token: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/token/refresh",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": UnauthorizedErrorResponse},
    },
    summary="Refresh Facturify authentication token",
    description="Refreshes the current authentication token or obtains a new one if refresh fails.",
)
async def refresh_token() -> AuthResponse:
    """Refresh the current authentication token."""
    try:
        client = await get_facturify_auth_client()
        result = await client.refresh_token()
        return AuthResponse(**result)
    except FacturifyAuthError as e:
        logger.error(f"Failed to refresh token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error refreshing token: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/token/status",
    response_model=TokenStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get token status",
    description="Returns the current status of the cached authentication token including TTL.",
)
async def get_token_status() -> TokenStatusResponse:
    """Get the status of the current token in cache."""
    try:
        token = await get_value("facturify:auth:token")
        
        if not token:
            return TokenStatusResponse(has_token=False, ttl=None, expires_in=None)
        
        ttl = await get_ttl("facturify:auth:token")
        expires_in_str = await get_value("facturify:auth:token_expiry")
        expires_in = int(expires_in_str) if expires_in_str else None
        
        return TokenStatusResponse(
            has_token=True,
            ttl=ttl if ttl > 0 else 0,
            expires_in=expires_in,
        )
    except Exception as e:
        logger.error(f"Error getting token status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/token",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get valid token",
    description="Returns a valid authentication token, automatically refreshing if needed.",
)
async def get_valid_token() -> dict:
    """Get a valid token, refreshing automatically if necessary."""
    try:
        client = await get_facturify_auth_client()
        token = await client.get_valid_token()
        ttl = await get_ttl("facturify:auth:token")
        
        return {
            "token": token,
            "ttl": ttl if ttl > 0 else 0,
        }
    except FacturifyAuthError as e:
        logger.error(f"Failed to get valid token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error getting valid token: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
