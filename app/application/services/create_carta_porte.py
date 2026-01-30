"""Caso de uso para timbrar CFDI de ingreso/traslado con Carta Porte."""
from __future__ import annotations

import json
import logging
from collections.abc import Callable

from app.application.dtos import CartaPorteRequest, PartyDTO
from app.application.ports.cfdi_provider import CFDIProvider
from app.application.ports.repositories import UnitOfWork
from app.core import exceptions
from app.domain import enums
from app.infrastructure.http.facturify_empresa_client import get_facturify_empresa_client
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
from app.infrastructure.mappers.facturify_payload import FacturifyPayloadBuilder

logger = logging.getLogger(__name__)

UnitOfWorkFactory = Callable[[], UnitOfWork]


class CreateCartaPorteService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        cfdi_provider: CFDIProvider,
        payload_builder: FacturifyPayloadBuilder,
    ) -> None:
        self._uow_factory = uow_factory
        self._cfdi_provider = cfdi_provider
        self._payload_builder = payload_builder

    async def execute(self, payload: CartaPorteRequest) -> Invoice:
        async with self._uow_factory() as uow:
            recipient = await uow.clients.get_by_rfc(payload.recipient.rfc)
            if recipient is None:
                recipient = await uow.clients.upsert(self._party_from_dto(payload.recipient))

            invoice = self._invoice_from_payload(payload, recipient)
            invoice.mark_pending()
            invoice = await uow.invoices.create(invoice)

        # Llamada externa y actualizacion de estado separada para evitar locks prolongados
        facturify_response: dict | None = None
        try:
            # Crear un Party temporal solo con el UUID de Facturify para el builder
            issuer = Party(
                legal_name="",
                rfc="",
                tax_regime="",
                email=None,
                address=Address(
                    street="",
                    exterior_number="",
                    neighborhood="",
                    city="",
                    state="",
                    country="MEX",
                    zip_code="00000",
                ),
                external_uuid=payload.facturify_issuer_uuid,
            )
            
            facturify_payload = self._payload_builder.build(invoice=invoice, issuer=issuer)
            facturify_response = await self._cfdi_provider.create_carta_porte(facturify_payload)
        except Exception as exc:  # pragma: no cover - logging en capa superior
            async with self._uow_factory() as uow:
                invoice.mark_failed()
                await uow.invoices.update(invoice)
            raise exceptions.ExternalServiceError(str(exc)) from exc

        data = facturify_response.get("data", {})
        cfdi_uuid = (
            data.get("cfdi_uuid")
            or facturify_response.get("cfdi_uuid")
            or data.get("cfdi", {}).get("cfdi_uuid")
        )
        if cfdi_uuid:
            invoice.mark_issued(
                uuid=cfdi_uuid,
                payload=facturify_response,
                serie=data.get("serie"),
                folio=data.get("folio"),
                factura_id=data.get("factura_id"),
                provider=data.get("provider"),
            )
        else:
            invoice.mark_failed()

        async with self._uow_factory() as uow:
            await uow.invoices.update(invoice)

        return invoice

    def _party_from_dto(self, dto: PartyDTO) -> Party:
        address = Address(
            street=dto.address.street,
            exterior_number=dto.address.exterior_number,
            neighborhood=dto.address.neighborhood,
            city=dto.address.city,
            state=dto.address.state,
            country=dto.address.country,
            zip_code=dto.address.zip_code,
        )
        return Party(
            legal_name=dto.legal_name,
            rfc=dto.rfc,
            tax_regime=dto.tax_regime,
            email=dto.email,
            address=address,
        )

    def _invoice_from_payload(self, payload: CartaPorteRequest, recipient: Party) -> Invoice:
        items = [
            InvoiceItem(
                product_key=item.product_key,
                description=item.description,
                quantity=item.quantity,
                unit_key=item.unit_key,
                unit_price=item.unit_price,
                taxes={"iva": item.tax_percentage} if item.tax_percentage else None,
            )
            for item in payload.items
        ]

        shipment = self._shipment_from_dto(payload)

        return Invoice(
            issuer_id=None,
            recipient=recipient,
            type=enums.InvoiceType(payload.cfdi_type),
            complement=enums.ComplementType.carta_porte,
            currency=payload.currency,
            subtotal=Money(amount=payload.subtotal, currency=payload.currency),
            total=Money(amount=payload.total, currency=payload.currency),
            cfdi_use=payload.cfdi_use,
            payment_form=payload.payment_form,
            payment_method=payload.payment_method,
            expedition_place=payload.expedition_place,
            items=items,
            shipment=shipment,
        )

    def _shipment_from_dto(self, payload: CartaPorteRequest) -> Shipment:
        dto = payload.shipment
        locations = [
            ShipmentLocation(
                type=item.type,
                datetime=item.datetime,
                street=item.street,
                exterior_number=item.exterior_number,
                neighborhood=item.neighborhood,
                city=item.city,
                state=item.state,
                country=item.country,
                zip_code=item.zip_code,
                latitude=item.latitude,
                longitude=item.longitude,
                reference=item.reference,
            )
            for item in dto.locations
        ]

        goods = [
            GoodsItem(
                description=item.description,
                product_key=item.product_key,
                quantity=item.quantity,
                unit_key=item.unit_key,
                weight_kg=item.weight_kg,
                value=item.value,
                dangerous_material=item.dangerous_material,
                dangerous_key=item.dangerous_key,
            )
            for item in dto.goods
        ]

        figures = [
            TransportFigure(
                type=figure.type,
                rfc=figure.rfc,
                name=figure.name,
                license=figure.license,
                role_description=figure.role_description,
            )
            for figure in dto.figures
        ]

        vehicle = Vehicle(
            configuration=dto.vehicle.configuration,
            plate=dto.vehicle.plate,
            federal_permit=dto.vehicle.federal_permit,
            insurance_company=dto.vehicle.insurance_company,
            insurance_policy=dto.vehicle.insurance_policy,
        )

        return Shipment(
            transport_mode=enums.TransportMode(dto.transport_mode),
            permit_type=dto.permit_type,
            permit_number=dto.permit_number,
            total_distance_km=dto.total_distance_km,
            total_weight_kg=dto.total_weight_kg,
            vehicle=vehicle,
            locations=locations,
            goods=goods,
            figures=figures,
        )
