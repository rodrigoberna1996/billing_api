"""Puertos de persistencia empleados por los casos de uso."""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities import Invoice, Party


class ClientGateway(Protocol):
    async def get_by_rfc(self, rfc: str) -> Party | None: ...

    async def upsert(self, party: Party) -> Party: ...


class InvoiceRepository(Protocol):
    async def create(self, invoice: Invoice) -> Invoice: ...

    async def update(self, invoice: Invoice) -> Invoice: ...

    async def get_by_id(self, invoice_id: UUID) -> Invoice | None: ...

    async def get_by_cfdi_uuid(self, cfdi_uuid: str) -> Invoice | None: ...

    async def get_pac_response_by_cfdi_uuid(self, cfdi_uuid: str) -> dict | None: ...

    async def list_by_trip_id(self, trip_id: int) -> list[Invoice]: ...


class UnitOfWork(Protocol):
    clients: ClientGateway
    invoices: InvoiceRepository

    async def __aenter__(self) -> "UnitOfWork": ...

    async def __aexit__(self, exc_type, exc, tb) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
