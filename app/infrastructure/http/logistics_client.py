"""Cliente HTTP para notificar a adrh_logistics después de un timbrado exitoso."""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class LogisticsClient:
    """Dispara un callback a adrh_logistics para asociar el CFDI con el viaje."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 10) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    async def notify_cfdi_issued(
        self,
        trip_id: int,
        cfdi_uuid: str,
        ccp: str | None = None,
    ) -> None:
        """Llama a PUT /internal/trips/{trip_id}/cfdi en adrh_logistics.

        Fire-and-forget: los errores se loguean pero no interrumpen la respuesta al cliente.
        """
        if not self._base_url or not self._api_key:
            logger.warning(
                "LOGISTICS_API_URL o LOGISTICS_API_KEY no configurados — "
                "omitiendo callback para trip_id=%s cfdi_uuid=%s",
                trip_id,
                cfdi_uuid,
            )
            return

        url = f"{self._base_url}/internal/trips/{trip_id}/cfdi"
        payload: dict = {"timbre_uuid": cfdi_uuid}
        if ccp:
            payload["ccp"] = ccp

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.put(
                    url,
                    json=payload,
                    headers={
                        "X-Internal-Key": self._api_key,
                        "Content-Type": "application/json",
                    },
                )
                if response.is_success:
                    logger.info(
                        "Callback logistics OK: trip_id=%s cfdi_uuid=%s",
                        trip_id,
                        cfdi_uuid,
                    )
                else:
                    logger.error(
                        "Callback logistics fallido HTTP %s: trip_id=%s cfdi_uuid=%s body=%s",
                        response.status_code,
                        trip_id,
                        cfdi_uuid,
                        response.text[:200],
                    )
        except Exception:
            logger.exception(
                "Error al notificar logistics (trip_id=%s cfdi_uuid=%s) — "
                "la factura fue timbrada correctamente",
                trip_id,
                cfdi_uuid,
            )

    async def notify_cfdi_cancelled(self, trip_id: int, cfdi_uuid: str) -> None:
        """Llama a DELETE /internal/trips/{trip_id}/cfdi para limpiar timbre_uuid/ccp.

        Fire-and-forget: los errores se loguean pero no interrumpen la respuesta al cliente.
        """
        if not self._base_url or not self._api_key:
            logger.warning(
                "LOGISTICS_API_URL o LOGISTICS_API_KEY no configurados — "
                "omitiendo callback de cancelación para trip_id=%s cfdi_uuid=%s",
                trip_id,
                cfdi_uuid,
            )
            return

        url = f"{self._base_url}/internal/trips/{trip_id}/cfdi"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.delete(
                    url,
                    headers={"X-Internal-Key": self._api_key},
                )
                if response.is_success:
                    logger.info(
                        "Callback logistics (cancelación) OK: trip_id=%s cfdi_uuid=%s",
                        trip_id,
                        cfdi_uuid,
                    )
                else:
                    logger.error(
                        "Callback logistics (cancelación) fallido HTTP %s: trip_id=%s "
                        "cfdi_uuid=%s body=%s",
                        response.status_code,
                        trip_id,
                        cfdi_uuid,
                        response.text[:200],
                    )
        except Exception:
            logger.exception(
                "Error al notificar cancelación a logistics (trip_id=%s cfdi_uuid=%s) — "
                "la factura fue cancelada correctamente",
                trip_id,
                cfdi_uuid,
            )
