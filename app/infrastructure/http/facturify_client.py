"""Cliente HTTP hacia Facturify basado en la especificacion publica."""
from __future__ import annotations

import logging

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.application.ports.cfdi_provider import CFDIProvider
from app.core.exceptions import ExternalServiceError
from app.infrastructure.http.facturify_auth_client import get_facturify_auth_client

logger = logging.getLogger(__name__)


class FacturifyClient(CFDIProvider):
    def __init__(
        self,
        base_url: str,
        timeout: float,
        max_retries: int,
        retry_backoff: float,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._retry = AsyncRetrying(
            reraise=True,
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=retry_backoff, min=retry_backoff, max=retry_backoff * 4),
            retry=retry_if_exception_type(httpx.RequestError),
        )

    async def create_carta_porte(self, payload: dict) -> dict:
        endpoint = f"{self._base_url}/api/v1/factura"
        return await self._post(endpoint, payload)

    async def get_invoice(self, cfdi_uuid: str) -> dict:
        endpoint = f"{self._base_url}/api/v1/factura/{cfdi_uuid}"
        return await self._get(endpoint)

    async def get_clients(self, limit: int = 50, offset: int = 0) -> dict:
        endpoint = f"{self._base_url}/api/v1/cliente/?limit={limit}&offset={offset}"
        return await self._get(endpoint)

    async def _post(self, url: str, payload: dict) -> dict:
        headers = await self._get_headers()
        async for attempt in self._retry:  # pragma: no branch - tenacity controla el flujo
            with attempt:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    return self._handle_response(response)
        raise ExternalServiceError("No se pudo contactar Facturify")

    async def _get(self, url: str) -> dict:
        headers = await self._get_headers()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url, headers=headers)
            return self._handle_response(response)

    async def _get_headers(self) -> dict[str, str]:
        auth_client = await get_facturify_auth_client()
        token = await auth_client.get_valid_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _handle_response(self, response: httpx.Response) -> dict:
        response_data = response.json()
        
        # Si la respuesta indica error (success=false), lanzar excepción con mensaje parseado
        if not response_data.get("success", True):
            from app.core.error_parser import FacturifyErrorParser
            
            import json
            logger.error("Respuesta completa de Facturify:")
            logger.error(json.dumps(response_data, indent=2, ensure_ascii=False))
            
            error_info = FacturifyErrorParser.parse_error(response_data)
            error_message = error_info["user_message"]
            
            logger.error("Mensaje parseado: %s", error_message)
            
            raise ExternalServiceError(error_message)
        
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - logging
            logger.error("Facturify HTTP error %s: %s", exc.response.status_code, exc.response.text)
            raise ExternalServiceError(exc.response.text) from exc
        
        return response_data
