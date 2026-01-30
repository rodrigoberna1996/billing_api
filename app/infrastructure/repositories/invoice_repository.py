"""Repositorio de facturas."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.repositories import InvoiceRepository
from app.domain import enums
from app.domain.entities import (
    Address,
    GoodsItem,
    Invoice,
    InvoiceItem,
    Money,
    Party,
    Shipment,
    ShipmentLocation,
    TransportFigure,
    Vehicle,
)
from app.infrastructure.orm import models


class SQLAlchemyInvoiceRepository(InvoiceRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, invoice: Invoice) -> Invoice:
        assert invoice.recipient.id is not None
        shipment = invoice.shipment
        if shipment is None:
            msg = "Las facturas de carta porte deben incluir envios"
            raise ValueError(msg)

        invoice_orm = models.InvoiceORM(
            id=invoice.id,
            issuer_id=invoice.issuer_id,
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
        )
        invoice_orm.items = [
            models.InvoiceItemORM(
                product_key=item.product_key,
                description=item.description,
                quantity=item.quantity,
                unit_key=item.unit_key,
                unit_price=item.unit_price,
                taxes=item.taxes,
            )
            for item in invoice.items
        ]

        shipment_orm = models.ShipmentORM(
            transport_mode=shipment.transport_mode.value,
            permit_type=shipment.permit_type,
            permit_number=shipment.permit_number,
            total_distance_km=shipment.total_distance_km,
            total_weight_kg=shipment.total_weight_kg,
            vehicle_configuration=shipment.vehicle.configuration,
            vehicle_plate=shipment.vehicle.plate,
            vehicle_permit=shipment.vehicle.federal_permit,
            insurance_company=shipment.vehicle.insurance_company,
            insurance_policy=shipment.vehicle.insurance_policy,
        )
        shipment_orm.locations = [
            models.ShipmentLocationORM(
                type=location.type.value,
                datetime=location.datetime,
                street=location.street,
                exterior_number=location.exterior_number,
                neighborhood=location.neighborhood,
                city=location.city,
                state=location.state,
                country=location.country,
                zip_code=location.zip_code,
                latitude=location.latitude,
                longitude=location.longitude,
                reference=location.reference,
            )
            for location in shipment.locations
        ]
        shipment_orm.goods = [
            models.ShipmentGoodsORM(
                description=good.description,
                product_key=good.product_key,
                quantity=good.quantity,
                unit_key=good.unit_key,
                weight_kg=good.weight_kg,
                value=good.value,
                dangerous_material=good.dangerous_material,
                dangerous_key=good.dangerous_key,
            )
            for good in shipment.goods
        ]
        shipment_orm.figures = [
            models.TransportFigureORM(
                type=figure.type,
                rfc=figure.rfc,
                name=figure.name,
                license=figure.license,
                role_description=figure.role_description,
            )
            for figure in shipment.figures
        ]
        invoice_orm.shipment = shipment_orm
        self._session.add(invoice_orm)
        await self._session.flush()
        return invoice

    async def update(self, invoice: Invoice) -> Invoice:
        stmt = select(models.InvoiceORM).where(models.InvoiceORM.id == invoice.id)
        result = await self._session.execute(stmt)
        invoice_orm = result.scalar_one()
        invoice_orm.status = invoice.status.value
        invoice_orm.facturify_uuid = invoice.facturify_uuid
        invoice_orm.facturify_payload = invoice.facturify_response
        invoice_orm.serie = invoice.serie
        invoice_orm.folio = invoice.folio
        invoice_orm.factura_id = invoice.factura_id
        invoice_orm.provider = invoice.provider
        await self._session.flush()
        return invoice

    async def get_by_id(self, invoice_id: UUID) -> Invoice | None:
        stmt = select(models.InvoiceORM).where(models.InvoiceORM.id == invoice_id)
        result = await self._session.execute(stmt)
        invoice_orm = result.scalar_one_or_none()
        if invoice_orm is None:
            return None
        return self._to_domain(invoice_orm)

    def _to_domain(self, invoice: models.InvoiceORM) -> Invoice:
        recipient = self._party_from_client(invoice.recipient)
        shipment = self._shipment_from_orm(invoice.shipment)
        items = [
            InvoiceItem(
                product_key=item.product_key,
                description=item.description,
                quantity=item.quantity,
                unit_key=item.unit_key,
                unit_price=item.unit_price,
                taxes=item.taxes,
            )
            for item in invoice.items
        ]
        domain_invoice = Invoice(
            id=invoice.id,
            issuer_id=str(invoice.issuer_id),
            recipient=recipient,
            type=enums.InvoiceType(invoice.cfdi_type),
            complement=enums.ComplementType(invoice.complement),
            currency=invoice.currency,
            subtotal=Money(invoice.subtotal, invoice.currency),
            total=Money(invoice.total, invoice.currency),
            cfdi_use=invoice.cfdi_use,
            payment_form=invoice.payment_form,
            payment_method=invoice.payment_method,
            expedition_place=invoice.expedition_place,
            items=items,
            shipment=shipment,
        )
        domain_invoice.status = enums.InvoiceStatus(invoice.status)
        domain_invoice.facturify_uuid = invoice.facturify_uuid
        domain_invoice.facturify_response = invoice.facturify_payload
        domain_invoice.serie = invoice.serie
        domain_invoice.folio = invoice.folio
        domain_invoice.factura_id = invoice.factura_id
        domain_invoice.provider = invoice.provider
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

    def _shipment_from_orm(self, shipment: models.ShipmentORM | None) -> Shipment | None:
        if shipment is None:
            return None
        locations = [
            ShipmentLocation(
                type=enums.ShipmentLocationType(location.type),
                datetime=location.datetime,
                street=location.street,
                exterior_number=location.exterior_number,
                neighborhood=location.neighborhood,
                city=location.city,
                state=location.state,
                country=location.country,
                zip_code=location.zip_code,
                latitude=location.latitude,
                longitude=location.longitude,
                reference=location.reference,
            )
            for location in shipment.locations
        ]
        goods = [
            GoodsItem(
                description=good.description,
                product_key=good.product_key,
                quantity=good.quantity,
                unit_key=good.unit_key,
                weight_kg=good.weight_kg,
                value=good.value,
                dangerous_material=good.dangerous_material,
                dangerous_key=good.dangerous_key,
            )
            for good in shipment.goods
        ]
        figures = [
            TransportFigure(
                type=figure.type,
                rfc=figure.rfc,
                name=figure.name,
                license=figure.license,
                role_description=figure.role_description,
            )
            for figure in shipment.figures
        ]
        vehicle = Vehicle(
            configuration=shipment.vehicle_configuration,
            plate=shipment.vehicle_plate,
            federal_permit=shipment.vehicle_permit,
            insurance_company=shipment.insurance_company,
            insurance_policy=shipment.insurance_policy,
        )
        return Shipment(
            transport_mode=enums.TransportMode(shipment.transport_mode),
            permit_type=shipment.permit_type,
            permit_number=shipment.permit_number,
            total_distance_km=shipment.total_distance_km,
            total_weight_kg=shipment.total_weight_kg,
            vehicle=vehicle,
            locations=locations,
            goods=goods,
            figures=figures,
        )
