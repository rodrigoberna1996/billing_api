"""Cliente HTTP hacia FacturaloPlus para timbrado de CFDI."""
from __future__ import annotations

import base64
import json
import logging
import re

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.application.ports.cfdi_provider import CFDIProvider
from app.core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)

_SAT_CODE_IN_MESSAGE = re.compile(r"\[([A-Z0-9]+)\]")


class FacturaloPlusClient(CFDIProvider):
    """Implementación de CFDIProvider usando FacturaloPlus como PAC."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        key_pem: str,
        cer_pem: str,
        csd_key_b64: str = "",
        csd_cer_b64: str = "",
        csd_password: str = "",
        emisor_rfc: str = "",
        pdf_plantilla: str = "",
        timeout: float = 30,
        max_retries: int = 3,
        retry_backoff: float = 2.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        # Normalizar a LF: archivos .env en Windows tienen CRLF que OpenSSL rechaza
        self._key_pem = key_pem.replace("\r\n", "\n").replace("\r", "\n")
        self._cer_pem = cer_pem.replace("\r\n", "\n").replace("\r", "\n")
        self._csd_key_b64 = csd_key_b64
        self._csd_cer_b64 = csd_cer_b64
        self._csd_password = csd_password
        self._emisor_rfc = emisor_rfc
        self._pdf_plantilla = pdf_plantilla.strip()
        self._timeout = timeout
        self._retry_kwargs = dict(
            reraise=True,
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=retry_backoff, min=retry_backoff, max=retry_backoff * 4),
            retry=retry_if_exception_type((httpx.ConnectError, httpx.ConnectTimeout, httpx.WriteTimeout)),
        )

    async def create_carta_porte(self, payload: dict) -> dict:
        """Timbra un CFDI Carta Porte.

        Usa timbrarJSON2 con plantilla PDF cuando está configurada; de lo contrario timbrarJSON3.
        """
        json_str = json.dumps(payload, ensure_ascii=False, indent=2)
        logger.debug("FacturaloPlus payload JSON:\n%s", json_str)

        json_b64 = base64.b64encode(json_str.encode("utf-8")).decode("ascii")

        form_data: dict = {
            "apikey": self._api_key,
            "jsonB64": json_b64,
            "keyPEM": self._key_pem,
            "cerPEM": self._cer_pem,
        }

        if self._pdf_plantilla:
            endpoint = f"{self._base_url}/api/rest/servicio/timbrarJSON2"
            form_data["plantilla"] = self._pdf_plantilla
            logger.info(
                "FacturaloPlus timbrarJSON2 plantilla=%s → %s",
                self._pdf_plantilla,
                endpoint,
            )
        else:
            endpoint = f"{self._base_url}/api/rest/servicio/timbrarJSON3"
            logger.info("FacturaloPlus timbrarJSON3 → %s", endpoint)

        return await self._post_form(endpoint, form_data)

    async def cancel_invoice(
        self,
        cfdi_uuid: str,
        rfc_receptor: str = "",
        total: str = "0",
        motivo: str = "02",
    ) -> dict:
        """Cancela un CFDI usando el endpoint cancelar2 de FacturaloPlus."""
        endpoint = f"{self._base_url}/api/rest/servicio/cancelar2"
        logger.info("FacturaloPlus cancelar2 uuid=%s motivo=%s", cfdi_uuid, motivo)

        return await self._post_form(endpoint, {
            "apikey": self._api_key,
            "keyCSD": self._csd_key_b64,
            "cerCSD": self._csd_cer_b64,
            "passCSD": self._csd_password,
            "uuid": cfdi_uuid,
            "rfcEmisor": self._emisor_rfc,
            "rfcReceptor": rfc_receptor,
            "total": total,
            "motivo": motivo,
        })

    async def get_invoice(self, cfdi_uuid: str) -> dict:
        """FacturaloPlus no expone endpoint de consulta; retorna dict con uuid."""
        return {"uuid": cfdi_uuid}

    async def _post_form(self, url: str, data: dict) -> dict:
        try:
            async for attempt in AsyncRetrying(**self._retry_kwargs):
                with attempt:
                    async with httpx.AsyncClient(timeout=self._timeout) as client:
                        response = await client.post(url, data=data)
                        return self._parse_response(response)
        except httpx.RequestError as exc:
            raise ExternalServiceError(
                f"No se pudo contactar FacturaloPlus tras los reintentos ({type(exc).__name__}). "
                "Considera aumentar FACTURALO_TIMEOUT si el payload es grande.",
                code="network_error",
            ) from exc
        raise ExternalServiceError(
            "No se pudo contactar FacturaloPlus tras los reintentos",
            code="network_error",
        )

    def _parse_response(self, response: httpx.Response) -> dict:
        try:
            body = response.json()
        except Exception as exc:
            raise ExternalServiceError(
                f"Respuesta no-JSON de FacturaloPlus (HTTP {response.status_code}): "
                f"{response.text[:300]}",
                code=str(response.status_code),
            ) from exc

        code = str(body.get("code", ""))
        if code != "200":
            message = body.get("message", "Error desconocido de FacturaloPlus")
            sat_code = self._extract_sat_code(message)
            logger.error(
                "FacturaloPlus error code=%s sat_code=%s message=%s",
                code,
                sat_code,
                message,
            )
            raise ExternalServiceError(
                message,
                code=sat_code or code,
            )

        raw_data = body.get("data", {})
        if isinstance(raw_data, str):
            try:
                body["data"] = json.loads(raw_data)
            except json.JSONDecodeError:
                pass

        return body

    @staticmethod
    def _extract_sat_code(message: str) -> str | None:
        match = _SAT_CODE_IN_MESSAGE.search(message)
        return match.group(1) if match else None
