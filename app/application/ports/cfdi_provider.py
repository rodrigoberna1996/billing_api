"""Puerto de comunicacion con proveedores de CFDI."""
from __future__ import annotations

from typing import Protocol


class CFDIProvider(Protocol):
    async def create_carta_porte(self, payload: dict) -> dict: ...

    async def get_invoice(self, cfdi_uuid: str) -> dict: ...

    async def cancel_invoice(
        self,
        cfdi_uuid: str,
        rfc_receptor: str = "",
        total: str = "0",
        motivo: str = "02",
        rfc_emisor: str = "",
        folio_sustitucion: str = "",
    ) -> dict: ...
