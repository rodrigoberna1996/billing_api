"""Unidad de trabajo para SQLAlchemy."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.ports.repositories import UnitOfWork
from app.infrastructure.repositories import (
    SQLAlchemyClientGateway,
    SQLAlchemyCompanyGateway,
    SQLAlchemyInvoiceRepository,
)


class SQLAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self.session: AsyncSession | None = None
        self.companies = None
        self.clients = None
        self.invoices = None

    async def __aenter__(self) -> "SQLAlchemyUnitOfWork":
        self.session = self._session_factory()
        self.companies = SQLAlchemyCompanyGateway(self.session)
        self.clients = SQLAlchemyClientGateway(self.session)
        self.invoices = SQLAlchemyInvoiceRepository(self.session)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        if self.session is None:
            return
        if exc:
            await self.session.rollback()
        else:
            await self.session.commit()
        await self.session.close()

    async def commit(self) -> None:
        if self.session is not None:
            await self.session.commit()

    async def rollback(self) -> None:
        if self.session is not None:
            await self.session.rollback()
