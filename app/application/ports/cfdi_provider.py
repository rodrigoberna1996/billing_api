"""Puerto de comunicacion con proveedores de CFDI."""
from __future__ import annotations

from typing import Protocol


class CFDIProvider(Protocol):
    async def create_carta_porte(self, payload: dict) -> dict: ...

    async def get_invoice(self, cfdi_uuid: str) -> dict: ...

    async def cancel_invoice(self, cfdi_uuid: str) -> dict: ...
