from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import ComplementType, InvoiceStatus, InvoiceType, ShipmentLocationType, TransportMode
from app.infrastructure.orm.base import Base, TimestampMixin, UUIDMixin


class CompanyORM(TimestampMixin, UUIDMixin, Base):
    __tablename__ = "companies"

    legal_name: Mapped[str] = mapped_column(String(255))
    rfc: Mapped[str] = mapped_column(String(13), unique=True, index=True)
    tax_regime: Mapped[str] = mapped_column(String(5))
    email: Mapped[str | None] = mapped_column(String(255))
    street: Mapped[str] = mapped_column(String(120))
    exterior_number: Mapped[str] = mapped_column(String(12))
    neighborhood: Mapped[str] = mapped_column(String(80))
    city: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(50))
    country: Mapped[str] = mapped_column(String(3), default="MEX")
    zip_code: Mapped[str] = mapped_column(String(5))
    facturify_uuid: Mapped[str] = mapped_column(String(36), unique=True)

    invoices: Mapped[list["InvoiceORM"]] = relationship("InvoiceORM", back_populates="issuer")


class ClientORM(TimestampMixin, UUIDMixin, Base):
    __tablename__ = "clients"

    legal_name: Mapped[str] = mapped_column(String(255))
    rfc: Mapped[str] = mapped_column(String(13), unique=True, index=True)
    tax_regime: Mapped[str] = mapped_column(String(5))
    email: Mapped[str | None] = mapped_column(String(255))
    street: Mapped[str] = mapped_column(String(120))
    exterior_number: Mapped[str] = mapped_column(String(12))
    neighborhood: Mapped[str] = mapped_column(String(80))
    city: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(50))
    country: Mapped[str] = mapped_column(String(3), default="MEX")
    zip_code: Mapped[str] = mapped_column(String(5))

    invoices: Mapped[list["InvoiceORM"]] = relationship("InvoiceORM", back_populates="recipient")


class InvoiceORM(TimestampMixin, UUIDMixin, Base):
    __tablename__ = "invoices"

    issuer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id"), index=True, nullable=True)
    recipient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    cfdi_type: Mapped[str] = mapped_column(String(16))
    complement: Mapped[str] = mapped_column(String(32))
    currency: Mapped[str] = mapped_column(String(3))
    subtotal: Mapped[float] = mapped_column(Float)
    total: Mapped[float] = mapped_column(Float)
    cfdi_use: Mapped[str] = mapped_column(String(5))
    payment_form: Mapped[str] = mapped_column(String(3))
    payment_method: Mapped[str] = mapped_column(String(3))
    expedition_place: Mapped[str] = mapped_column(String(5))
    status: Mapped[str] = mapped_column(String(16), default=InvoiceStatus.draft.value)
    facturify_uuid: Mapped[str | None] = mapped_column(String(64))
    facturify_payload: Mapped[dict | None] = mapped_column(JSONB)
    serie: Mapped[str | None] = mapped_column(String(10))
    folio: Mapped[int | None]
    factura_id: Mapped[str | None] = mapped_column(String(50))
    provider: Mapped[str | None] = mapped_column(String(10))

    issuer: Mapped[CompanyORM | None] = relationship("CompanyORM", back_populates="invoices")
    recipient: Mapped[ClientORM] = relationship("ClientORM", back_populates="invoices")
    items: Mapped[list["InvoiceItemORM"]] = relationship("InvoiceItemORM", back_populates="invoice", cascade="all, delete-orphan")
    shipment: Mapped[ShipmentORM | None] = relationship("ShipmentORM", back_populates="invoice", uselist=False, cascade="all, delete-orphan")


class InvoiceItemORM(UUIDMixin, Base):
    __tablename__ = "invoice_items"

    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"))
    product_key: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text)
    quantity: Mapped[float]
    unit_key: Mapped[str] = mapped_column(String(10))
    unit_price: Mapped[float]
    taxes: Mapped[dict | None] = mapped_column(JSONB)

    invoice: Mapped[InvoiceORM] = relationship("InvoiceORM", back_populates="items")


class ShipmentORM(UUIDMixin, Base):
    __tablename__ = "shipments"

    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), unique=True)
    transport_mode: Mapped[str] = mapped_column(String(5))
    permit_type: Mapped[str] = mapped_column(String(10))
    permit_number: Mapped[str] = mapped_column(String(30))
    total_distance_km: Mapped[float | None] = mapped_column(Float)
    total_weight_kg: Mapped[float] = mapped_column(Float)

    vehicle_configuration: Mapped[str] = mapped_column(String(10))
    vehicle_plate: Mapped[str] = mapped_column(String(10))
    vehicle_permit: Mapped[str | None] = mapped_column(String(30))
    insurance_company: Mapped[str | None] = mapped_column(String(120))
    insurance_policy: Mapped[str | None] = mapped_column(String(80))

    invoice: Mapped[InvoiceORM] = relationship("InvoiceORM", back_populates="shipment")
    locations: Mapped[list["ShipmentLocationORM"]] = relationship("ShipmentLocationORM", back_populates="shipment", cascade="all, delete-orphan")
    goods: Mapped[list["ShipmentGoodsORM"]] = relationship("ShipmentGoodsORM", back_populates="shipment", cascade="all, delete-orphan")
    figures: Mapped[list["TransportFigureORM"]] = relationship("TransportFigureORM", back_populates="shipment", cascade="all, delete-orphan")


class ShipmentLocationORM(UUIDMixin, Base):
    __tablename__ = "shipment_locations"

    shipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"))
    type: Mapped[ShipmentLocationType] = mapped_column(String(16))
    datetime: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    street: Mapped[str] = mapped_column(String(120))
    exterior_number: Mapped[str] = mapped_column(String(12))
    neighborhood: Mapped[str] = mapped_column(String(80))
    city: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(50))
    country: Mapped[str] = mapped_column(String(3))
    zip_code: Mapped[str] = mapped_column(String(5))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    reference: Mapped[str | None] = mapped_column(String(200))

    shipment: Mapped[ShipmentORM] = relationship("ShipmentORM", back_populates="locations")


class ShipmentGoodsORM(UUIDMixin, Base):
    __tablename__ = "shipment_goods"

    shipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"))
    description: Mapped[str] = mapped_column(String(255))
    product_key: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[float]
    unit_key: Mapped[str] = mapped_column(String(10))
    weight_kg: Mapped[float]
    value: Mapped[float]
    dangerous_material: Mapped[bool] = mapped_column(Boolean, default=False)
    dangerous_key: Mapped[str | None] = mapped_column(String(10))

    shipment: Mapped[ShipmentORM] = relationship("ShipmentORM", back_populates="goods")


class TransportFigureORM(UUIDMixin, Base):
    __tablename__ = "transport_figures"

    shipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(4))
    rfc: Mapped[str] = mapped_column(String(13))
    name: Mapped[str] = mapped_column(String(255))
    license: Mapped[str | None] = mapped_column(String(20))
    role_description: Mapped[str | None] = mapped_column(String(120))

    shipment: Mapped[ShipmentORM] = relationship("ShipmentORM", back_populates="figures")
