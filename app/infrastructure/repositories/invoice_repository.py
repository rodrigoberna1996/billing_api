"""Repositorio de facturas."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only, selectinload

from app.application.ports.repositories import InvoiceRepository
from app.domain import enums
from app.domain.entities import Address, Invoice, Money, Party
from app.infrastructure.orm import models


class SQLAlchemyInvoiceRepository(InvoiceRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, invoice: Invoice) -> Invoice:
        assert invoice.recipient.id is not None

        # Reserva atómica de serie/folio desde invoice_settings (editable en "Mi cuenta").
        # El UPDATE...RETURNING sobre la fila única id=1 es tan seguro ante concurrencia
        # como nextval() en una secuencia (Postgres serializa updates sobre la misma fila).
        result = await self._session.execute(
            text(
                "UPDATE invoice_settings "
                "SET next_folio = next_folio + 1, updated_at = now() "
                "WHERE id = 1 "
                "RETURNING serie, next_folio - 1 AS folio"
            )
        )
        row = result.first()
        if row is None:
            msg = (
                "invoice_settings no está inicializada; ejecuta las migraciones "
                "(alembic upgrade) antes de timbrar."
            )
            raise RuntimeError(msg)
        serie, folio = row.serie, row.folio

        orm = models.InvoiceORM(
            id=invoice.id,
            recipient_id=invoice.recipient.id,
            cfdi_type=invoice.type.value,
            complement=invoice.complement.value,
            currency=invoice.currency,
            subtotal=invoice.subtotal.amount,
            total=invoice.total.amount,
            cfdi_use=invoice.cfdi_use,
            payment_form=invoice.payment_form,
            payment_method=invoice.payment_method,
            expedition_place=invoice.expedition_place,
            status=invoice.status.value,
            trip_id=invoice.trip_id,
            serie=serie,
            folio=folio,
            form_snapshot=invoice.form_snapshot,
        )
        self._session.add(orm)
        await self._session.flush()
        invoice.serie = serie
        invoice.folio = folio
        return invoice

    async def update(self, invoice: Invoice) -> Invoice:
        stmt = select(models.InvoiceORM).where(models.InvoiceORM.id == invoice.id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one()
        orm.status = invoice.status.value
        orm.cfdi_uuid = invoice.cfdi_uuid
        orm.pac_response = invoice.pac_response
        orm.cfdi_xml = invoice.cfdi_xml
        orm.cfdi_pdf_b64 = invoice.cfdi_pdf_b64
        orm.serie = invoice.serie
        orm.folio = invoice.folio
        orm.provider = invoice.provider
        orm.form_snapshot = invoice.form_snapshot
        orm.cancelled_at = invoice.cancelled_at
        orm.cancel_motivo = invoice.cancel_motivo
        orm.cancel_response = invoice.cancel_response
        await self._session.flush()
        return invoice

    async def get_by_id(self, invoice_id: UUID) -> Invoice | None:
        stmt = (
            select(models.InvoiceORM)
            .where(models.InvoiceORM.id == invoice_id)
            .options(selectinload(models.InvoiceORM.recipient))
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        return self._to_domain(orm)

    async def get_by_cfdi_uuid(self, cfdi_uuid: str) -> Invoice | None:
        stmt = (
            select(models.InvoiceORM)
            .where(models.InvoiceORM.cfdi_uuid == cfdi_uuid)
            .options(selectinload(models.InvoiceORM.recipient))
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        return self._to_domain(orm)

    async def list_by_trip_id(self, trip_id: int) -> list[Invoice]:
        """Historial de facturas (issued/canceled/failed) de un viaje, más reciente primero."""
        stmt = (
            select(models.InvoiceORM)
            .where(models.InvoiceORM.trip_id == trip_id)
            .options(selectinload(models.InvoiceORM.recipient))
            .order_by(models.InvoiceORM.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(orm) for orm in result.scalars().all()]

    async def get_max_folio(self) -> int | None:
        """Último folio ya asignado (usado para validar que no se pueda retroceder el contador)."""
        result = await self._session.execute(select(func.max(models.InvoiceORM.folio)))
        return result.scalar_one_or_none()

    async def get_pac_response_by_cfdi_uuid(self, cfdi_uuid: str) -> dict | None:
        """Carga solo los campos de documentos (pac_response, cfdi_xml, cfdi_pdf_b64) sin relaciones."""
        stmt = (
            select(models.InvoiceORM)
            .where(models.InvoiceORM.cfdi_uuid == cfdi_uuid)
            .options(load_only(
                models.InvoiceORM.pac_response,
                models.InvoiceORM.cfdi_xml,
                models.InvoiceORM.cfdi_pdf_b64,
            ))
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        return {
            "pac_response": orm.pac_response or {},
            "cfdi_xml": orm.cfdi_xml,
            "cfdi_pdf_b64": orm.cfdi_pdf_b64,
        }

    def _to_domain(self, orm: models.InvoiceORM) -> Invoice:
        recipient = self._party_from_client(orm.recipient)
        domain_invoice = Invoice(
            id=orm.id,
            recipient=recipient,
            type=enums.InvoiceType(orm.cfdi_type),
            complement=enums.ComplementType(orm.complement),
            currency=orm.currency,
            subtotal=Money(orm.subtotal, orm.currency),
            total=Money(orm.total, orm.currency),
            cfdi_use=orm.cfdi_use,
            payment_form=orm.payment_form,
            payment_method=orm.payment_method,
            expedition_place=orm.expedition_place,
        )
        domain_invoice.status = enums.InvoiceStatus(orm.status)
        domain_invoice.cfdi_uuid = orm.cfdi_uuid
        domain_invoice.pac_response = orm.pac_response
        domain_invoice.cfdi_xml = orm.cfdi_xml
        domain_invoice.cfdi_pdf_b64 = orm.cfdi_pdf_b64
        domain_invoice.trip_id = orm.trip_id
        domain_invoice.serie = orm.serie
        domain_invoice.folio = orm.folio
        domain_invoice.provider = orm.provider
        domain_invoice.form_snapshot = orm.form_snapshot
        domain_invoice.cancelled_at = orm.cancelled_at
        domain_invoice.cancel_motivo = orm.cancel_motivo
        domain_invoice.cancel_response = orm.cancel_response
        domain_invoice.created_at = orm.created_at
        domain_invoice.updated_at = orm.updated_at
        return domain_invoice

    def _party_from_client(self, client: models.ClientORM) -> Party:
        return Party(
            id=client.id,
            legal_name=client.legal_name,
            rfc=client.rfc,
            tax_regime=client.tax_regime,
            email=client.email,
            address=Address(
                street=client.street,
                exterior_number=client.exterior_number,
                neighborhood=client.neighborhood,
                city=client.city,
                state=client.state,
                country=client.country,
                zip_code=client.zip_code,
            ),
        )
