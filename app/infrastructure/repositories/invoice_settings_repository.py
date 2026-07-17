"""Repositorio de configuración de serie/folio (fila única, editable desde 'Mi cuenta')."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.repositories import InvoiceSettingsRepository
from app.domain.entities import InvoiceSettings
from app.infrastructure.orm import models

SETTINGS_ROW_ID = 1


class SQLAlchemyInvoiceSettingsRepository(InvoiceSettingsRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self) -> InvoiceSettings:
        orm = await self._get_orm()
        return InvoiceSettings(serie=orm.serie, next_folio=orm.next_folio, updated_at=orm.updated_at)

    async def update(self, serie: str, next_folio: int) -> InvoiceSettings:
        orm = await self._get_orm()
        orm.serie = serie
        orm.next_folio = next_folio
        await self._session.flush()
        return InvoiceSettings(serie=orm.serie, next_folio=orm.next_folio, updated_at=orm.updated_at)

    async def _get_orm(self) -> models.InvoiceSettingsORM:
        stmt = select(models.InvoiceSettingsORM).where(
            models.InvoiceSettingsORM.id == SETTINGS_ROW_ID
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            msg = (
                "invoice_settings no está inicializada; ejecuta las migraciones "
                "(alembic upgrade) antes de usar esta funcionalidad."
            )
            raise LookupError(msg)
        return orm
