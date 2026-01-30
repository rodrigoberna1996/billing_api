"""Facturify empresa (company) client."""
from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.infrastructure.http.facturify_auth_client import get_facturify_auth_client

logger = logging.getLogger(__name__)


class FacturifyEmpresaError(Exception):
    """Base exception for Facturify empresa errors."""
    pass


class FacturifyEmpresaClient:
    """Client for Facturify empresa endpoints."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._http_client: httpx.AsyncClient | None = None

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
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        logger.info("Facturify empresa client closed")

    async def _get_auth_headers(self) -> dict[str, str]:
        """Get authorization headers with valid token."""
        auth_client = await get_facturify_auth_client()
        token = await auth_client.get_valid_token()
        return {"Authorization": f"Bearer {token}"}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def get_empresas(self) -> dict[str, Any]:
        """Get all empresas from Facturify with pagination metadata."""
        client = await self._get_http_client()
        headers = await self._get_auth_headers()

        try:
            response = await client.get("/api/v1/empresa/", headers=headers)

            if response.status_code == 200:
                response_data = response.json()
                empresas = response_data.get("data", [])
                logger.info(f"Retrieved {len(empresas)} empresas from Facturify")
                return response_data
            elif response.status_code == 401:
                error_data = response.json()
                logger.error(f"Unauthorized accessing empresas: {error_data.get('message')}")
                raise FacturifyEmpresaError(f"Unauthorized: {error_data.get('message')}")
            else:
                logger.error(f"Unexpected response getting empresas: {response.status_code}")
                raise FacturifyEmpresaError(f"Unexpected response: {response.status_code}")

        except httpx.HTTPError as e:
            logger.error(f"HTTP error getting empresas: {e}")
            raise FacturifyEmpresaError(f"HTTP error: {e}") from e

    async def get_empresa_by_rfc(self, rfc: str) -> dict[str, Any] | None:
        """Get empresa by RFC."""
        response_data = await self.get_empresas()
        empresas = response_data.get("data", [])
        
        rfc_normalized = rfc.strip().upper()
        
        for empresa in empresas:
            empresa_rfc = empresa.get("rfc", "").strip().upper()
            if empresa_rfc == rfc_normalized:
                logger.info(f"Found empresa with RFC: {rfc}")
                return empresa
        
        logger.warning(f"No empresa found with RFC: {rfc}")
        return None


_empresa_client: FacturifyEmpresaClient | None = None


async def get_facturify_empresa_client() -> FacturifyEmpresaClient:
    """Get or create Facturify empresa client singleton."""
    global _empresa_client
    if _empresa_client is None:
        _empresa_client = FacturifyEmpresaClient()
    return _empresa_client


async def close_facturify_empresa_client() -> None:
    """Close Facturify empresa client."""
    global _empresa_client
    if _empresa_client is not None:
        await _empresa_client.close()
        _empresa_client = None
