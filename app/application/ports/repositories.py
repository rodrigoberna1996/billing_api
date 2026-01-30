"""Puertos de persistencia empleados por los casos de uso."""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities import Invoice, Party


class CompanyGateway(Protocol):
    async def get_by_id(self, company_id: UUID) -> Party | None: ...
    
    async def get_by_rfc(self, rfc: str) -> Party | None: ...
    
    async def create(self, party: Party) -> Party: ...


class ClientGateway(Protocol):
    async def get_by_rfc(self, rfc: str) -> Party | None: ...

    async def upsert(self, party: Party) -> Party: ...


class InvoiceRepository(Protocol):
    async def create(self, invoice: Invoice) -> Invoice: ...

    async def update(self, invoice: Invoice) -> Invoice: ...

    async def get_by_id(self, invoice_id: UUID) -> Invoice | None: ...


class UnitOfWork(Protocol):
    companies: CompanyGateway
    clients: ClientGateway
    invoices: InvoiceRepository

    async def __aenter__(self) -> "UnitOfWork": ...

    async def __aexit__(self, exc_type, exc, tb) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
