"""Facturify authentication client with token management."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx
import orjson
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.redis import delete_key, get_ttl, get_value, set_with_expiry

logger = logging.getLogger(__name__)

FACTURIFY_TOKEN_KEY = "facturify:auth:token"
FACTURIFY_TOKEN_EXPIRY_KEY = "facturify:auth:token_expiry"


class FacturifyAuthError(Exception):
    """Base exception for Facturify authentication errors."""
    pass


class FacturifyAuthClient:
    """Client for managing Facturify authentication and token lifecycle."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._http_client: httpx.AsyncClient | None = None
        self._refresh_task: asyncio.Task | None = None
        self._shutdown = False

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=self.settings.facturify_base_url,
                timeout=httpx.Timeout(self.settings.facturify_timeout),
                headers={"Content-Type": "application/json"},
            )
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client and stop refresh task."""
        self._shutdown = True
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        logger.info("Facturify auth client closed")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def obtain_token(self) -> dict[str, Any]:
        """Obtain a new token from Facturify API."""
        client = await self._get_http_client()
        
        payload = {
            "api_key": self.settings.facturify_api_key,
            "api_secret": self.settings.facturify_api_secret,
        }

        try:
            response = await client.post("/api/v1/auth", json=payload)
            
            if response.status_code == 200:
                data = response.json()
                token = data["jwt"]["token"]
                expires_in = data["jwt"]["expires_in"]
                
                await set_with_expiry(FACTURIFY_TOKEN_KEY, token, expires_in)
                await set_with_expiry(
                    FACTURIFY_TOKEN_EXPIRY_KEY,
                    str(expires_in),
                    expires_in,
                )
                
                logger.info(f"Facturify initial token obtained (expires in {expires_in}s), will refresh immediately to get long-lived token")
                return data
            elif response.status_code == 401:
                error_data = response.json()
                logger.error(f"Facturify authentication failed: {error_data.get('message')}")
                raise FacturifyAuthError(f"Authentication failed: {error_data.get('message')}")
            elif response.status_code == 422:
                error_data = response.json()
                errors = error_data.get("errors", [])
                error_messages = [f"{e.get('field')}: {e.get('message')}" for e in errors]
                logger.error(f"Facturify validation error: {error_messages}")
                raise FacturifyAuthError(f"Validation error: {', '.join(error_messages)}")
            else:
                logger.error(f"Unexpected response from Facturify: {response.status_code}")
                raise FacturifyAuthError(f"Unexpected response: {response.status_code}")
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error obtaining Facturify token: {e}")
            raise FacturifyAuthError(f"HTTP error: {e}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def refresh_token(self) -> dict[str, Any]:
        """Refresh the current token."""
        current_token = await get_value(FACTURIFY_TOKEN_KEY)
        
        if not current_token:
            logger.warning("No token found in cache, obtaining new token")
            return await self.obtain_token()

        client = await self._get_http_client()
        
        try:
            response = await client.post(
                "/api/v1/token/refresh",
                headers={"Authorization": f"Bearer {current_token}"},
            )
            
            if response.status_code == 200:
                data = response.json()
                token = data["jwt"]["token"]
                expires_in = data["jwt"]["expires_in"]
                
                await set_with_expiry(FACTURIFY_TOKEN_KEY, token, expires_in)
                await set_with_expiry(
                    FACTURIFY_TOKEN_EXPIRY_KEY,
                    str(expires_in),
                    expires_in,
                )
                
                logger.info(f"Facturify token refreshed successfully (expires in {expires_in}s = {expires_in/3600:.1f} hours)")
                return data
            elif response.status_code == 401:
                error_data = response.json()
                logger.warning(f"Token refresh failed, obtaining new token: {error_data.get('message')}")
                return await self.obtain_token()
            else:
                logger.error(f"Unexpected response refreshing token: {response.status_code}")
                raise FacturifyAuthError(f"Unexpected response: {response.status_code}")
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error refreshing Facturify token: {e}")
            raise FacturifyAuthError(f"HTTP error: {e}") from e

    async def get_valid_token(self) -> str:
        """Get a valid token, refreshing if necessary."""
        token = await get_value(FACTURIFY_TOKEN_KEY)
        
        if not token:
            logger.info("No token in cache, obtaining new token")
            result = await self.obtain_token()
            return result["jwt"]["token"]
        
        ttl = await get_ttl(FACTURIFY_TOKEN_KEY)
        
        if ttl < self.settings.facturify_token_refresh_buffer:
            logger.info(f"Token expiring soon (TTL: {ttl}s), refreshing")
            result = await self.refresh_token()
            return result["jwt"]["token"]
        
        return token

    async def start_background_refresh(self) -> None:
        """Start background task to automatically refresh token."""
        if self._refresh_task and not self._refresh_task.done():
            logger.warning("Background refresh task already running")
            return
        
        self._refresh_task = asyncio.create_task(self._background_refresh_loop())
        logger.info("Background token refresh task started")

    async def _background_refresh_loop(self) -> None:
        """Background loop to refresh token before expiry.
        
        Strategy:
        1. If no token exists, obtain initial token (240s) then immediately refresh to get long-lived token (43200s)
        2. Always maintain the long-lived refresh token by refreshing before expiry
        3. Only use /auth endpoint when refresh fails (token expired or invalid)
        """
        while not self._shutdown:
            try:
                token = await get_value(FACTURIFY_TOKEN_KEY)
                
                if not token:
                    logger.info("No token found, obtaining initial token then refreshing for long-lived token")
                    await self.obtain_token()
                    await asyncio.sleep(5)
                    logger.info("Refreshing initial token to get long-lived token (43200s)")
                    await self.refresh_token()
                    await asyncio.sleep(60)
                    continue
                
                ttl = await get_ttl(FACTURIFY_TOKEN_KEY)
                expires_in_str = await get_value(FACTURIFY_TOKEN_EXPIRY_KEY)
                original_expiry = int(expires_in_str) if expires_in_str else None
                
                if ttl <= 0:
                    logger.warning("Token expired, obtaining new token and refreshing")
                    await self.obtain_token()
                    await asyncio.sleep(5)
                    await self.refresh_token()
                    await asyncio.sleep(60)
                    continue
                
                if original_expiry and original_expiry < 300:
                    logger.info(f"Short-lived token detected ({original_expiry}s), refreshing to get long-lived token")
                    await self.refresh_token()
                    await asyncio.sleep(60)
                    continue
                
                refresh_at = ttl - self.settings.facturify_token_refresh_buffer
                
                if refresh_at > 0:
                    wait_time = min(refresh_at, 300)
                    logger.debug(f"Long-lived token valid (TTL: {ttl}s = {ttl/3600:.1f}h), will check again in {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    logger.info(f"Token expiring soon (TTL: {ttl}s), refreshing to maintain long-lived token")
                    await self.refresh_token()
                    await asyncio.sleep(60)
                    
            except asyncio.CancelledError:
                logger.info("Background refresh task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in background refresh loop: {e}", exc_info=True)
                await asyncio.sleep(30)


_auth_client: FacturifyAuthClient | None = None


async def get_facturify_auth_client() -> FacturifyAuthClient:
    """Get or create Facturify auth client singleton."""
    global _auth_client
    if _auth_client is None:
        _auth_client = FacturifyAuthClient()
    return _auth_client


async def close_facturify_auth_client() -> None:
    """Close Facturify auth client."""
    global _auth_client
    if _auth_client is not None:
        await _auth_client.close()
        _auth_client = None
