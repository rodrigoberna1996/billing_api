"""Repositorio de facturas."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
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
            form_snapshot=invoice.form_snapshot,
        )
        self._session.add(orm)
        await self._session.flush()
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
