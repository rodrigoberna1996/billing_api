from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID, uuid4

from app.domain.enums import (
    ComplementType,
    InvoiceStatus,
    InvoiceType,
    ShipmentLocationType,
    TransportMode,
)


@dataclass(frozen=True, slots=True)
class Money:
    amount: float
    currency: str = "MXN"

    def __post_init__(self) -> None:
        if self.amount < 0:
            msg = "El monto no puede ser negativo"
            raise ValueError(msg)


@dataclass(slots=True)
class Address:
    street: str
    exterior_number: str
    neighborhood: str
    city: str
    state: str
    country: str
    zip_code: str


@dataclass(slots=True)
class Party:
    legal_name: str
    rfc: str
    tax_regime: str
    email: str | None
    address: Address
    external_uuid: str | None = None
    id: UUID | None = None


@dataclass(slots=True)
class Vehicle:
    configuration: str
    plate: str
    federal_permit: str | None = None
    insurance_company: str | None = None
    insurance_policy: str | None = None


@dataclass(slots=True)
class GoodsItem:
    description: str
    product_key: str
    quantity: float
    unit_key: str
    weight_kg: float
    value: float
    dangerous_material: bool = False
    dangerous_key: str | None = None


@dataclass(slots=True)
class ShipmentLocation:
    type: ShipmentLocationType
    datetime: datetime
    street: str
    exterior_number: str
    neighborhood: str
    city: str
    state: str
    country: str
    zip_code: str
    latitude: float | None = None
    longitude: float | None = None
    reference: str | None = None


@dataclass(slots=True)
class TransportFigure:
    type: str
    rfc: str
    name: str
    license: str | None = None
    role_description: str | None = None


@dataclass(slots=True)
class Shipment:
    transport_mode: TransportMode
    permit_type: str
    permit_number: str
    total_distance_km: float | None
    total_weight_kg: float
    vehicle: Vehicle
    locations: Sequence[ShipmentLocation] = field(default_factory=list)
    goods: Sequence[GoodsItem] = field(default_factory=list)
    figures: Sequence[TransportFigure] = field(default_factory=list)


@dataclass(slots=True)
class InvoiceItem:
    product_key: str
    description: str
    quantity: float
    unit_key: str
    unit_price: float
    taxes: dict[str, float] | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class Invoice:
    issuer_id: UUID | None
    recipient: Party
    type: InvoiceType
    complement: ComplementType
    currency: str
    subtotal: Money
    total: Money
    cfdi_use: str
    payment_form: str
    payment_method: str
    expedition_place: str
    items: Sequence[InvoiceItem] = field(default_factory=list)
    shipment: Shipment | None = None
    status: InvoiceStatus = InvoiceStatus.draft
    facturify_uuid: str | None = None
    facturify_response: dict | None = None
    serie: str | None = None
    folio: int | None = None
    factura_id: str | None = None
    provider: str | None = None
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    id: UUID = field(default_factory=uuid4)

    def mark_pending(self) -> None:
        self.status = InvoiceStatus.pending

    def mark_issued(
        self,
        uuid: str,
        payload: dict,
        serie: str | None = None,
        folio: int | None = None,
        factura_id: str | None = None,
        provider: str | None = None,
    ) -> None:
        self.status = InvoiceStatus.issued
        self.facturify_uuid = uuid
        self.facturify_response = payload
        self.serie = serie
        self.folio = folio
        self.factura_id = factura_id
        self.provider = provider
        self.updated_at = _utc_now()

    def mark_failed(self) -> None:
        self.status = InvoiceStatus.failed
        self.updated_at = _utc_now()


__all__ = [
    "Address",
    "GoodsItem",
    "Invoice",
    "InvoiceItem",
    "Money",
    "Party",
    "Shipment",
    "ShipmentLocation",
    "TransportFigure",
    "Vehicle",
]
