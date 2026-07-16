from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import InvoiceStatus
from app.infrastructure.orm.base import Base, TimestampMixin, UUIDMixin


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

    recipient_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("clients.id"), index=True
    )
    cfdi_type: Mapped[str] = mapped_column(String(16))
    complement: Mapped[str] = mapped_column(String(32))
    currency: Mapped[str] = mapped_column(String(3))
    subtotal: Mapped[float] = mapped_column(Float)
    total: Mapped[float] = mapped_column(Float)
    cfdi_use: Mapped[str] = mapped_column(String(5))
    payment_form: Mapped[str | None] = mapped_column(String(3))
    payment_method: Mapped[str | None] = mapped_column(String(3))
    expedition_place: Mapped[str] = mapped_column(String(5))
    status: Mapped[str] = mapped_column(String(16), default=InvoiceStatus.draft.value)

    cfdi_uuid: Mapped[str | None] = mapped_column(String(64), index=True, unique=True)
    pac_response: Mapped[dict | None] = mapped_column(JSONB)
    cfdi_xml: Mapped[str | None] = mapped_column(Text)
    cfdi_pdf_b64: Mapped[str | None] = mapped_column(Text)

    trip_id: Mapped[int | None] = mapped_column(Integer, index=True)

    serie: Mapped[str | None] = mapped_column(String(10))
    folio: Mapped[int | None]
    provider: Mapped[str | None] = mapped_column(String(20))
    form_snapshot: Mapped[dict | None] = mapped_column(JSONB)

    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_motivo: Mapped[str | None] = mapped_column(String(2))
    cancel_response: Mapped[dict | None] = mapped_column(JSONB)

    recipient: Mapped[ClientORM] = relationship("ClientORM", back_populates="invoices")
