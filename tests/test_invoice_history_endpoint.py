"""Pruebas de GET /v1/cfdi/by-trip/{trip_id} — historial de facturas de un viaje."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.domain.entities import Address, Invoice, Money, Party
from app.domain.enums import ComplementType, InvoiceStatus, InvoiceType
from app.interfaces.api.routers.carta_porte import get_invoice_history_by_trip_endpoint

TRIP_ID = 712


def _invoice(
    status_: InvoiceStatus,
    *,
    cfdi_uuid: str | None,
    folio: int | None,
    cancel_motivo: str | None = None,
    cancelled_at: datetime | None = None,
    created_at: datetime | None = None,
) -> Invoice:
    invoice = Invoice(
        recipient=Party(
            legal_name="Cliente de prueba",
            rfc="XAXX010101000",
            tax_regime="616",
            email=None,
            address=Address(
                street="Calle 1",
                exterior_number="1",
                neighborhood="Centro",
                city="Puebla",
                state="Puebla",
                country="MEX",
                zip_code="72000",
            ),
        ),
        type=InvoiceType.ingreso,
        complement=ComplementType.carta_porte,
        currency="MXN",
        subtotal=Money(amount=100.0),
        total=Money(amount=116.0),
        cfdi_use="S01",
        payment_form="99",
        payment_method="PPD",
        expedition_place="76800",
        status=status_,
        cfdi_uuid=cfdi_uuid,
        serie="CCP",
        folio=folio,
        trip_id=TRIP_ID,
        cancel_motivo=cancel_motivo,
        cancelled_at=cancelled_at,
    )
    if created_at is not None:
        invoice.created_at = created_at
    return invoice


class _FakeInvoiceRepo:
    def __init__(self, invoices: list[Invoice]) -> None:
        self._invoices = invoices

    async def list_by_trip_id(self, trip_id: int) -> list[Invoice]:
        return [inv for inv in self._invoices if inv.trip_id == trip_id]


class _FakeUow:
    def __init__(self, repo: _FakeInvoiceRepo) -> None:
        self.invoices = repo

    async def __aenter__(self) -> "_FakeUow":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None


def _uow_factory(invoices: list[Invoice]):
    repo = _FakeInvoiceRepo(invoices)

    def factory() -> _FakeUow:
        return _FakeUow(repo)

    return factory


async def test_history_empty_when_no_invoices_for_trip() -> None:
    result = await get_invoice_history_by_trip_endpoint(
        trip_id=TRIP_ID, uow_factory=_uow_factory([])
    )
    assert result.trip_id == TRIP_ID
    assert result.invoices == []


async def test_history_includes_cancelled_invoice_with_pdf_xml_urls() -> None:
    cancelled_at = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    invoice = _invoice(
        InvoiceStatus.canceled,
        cfdi_uuid="93fafe6c-5bd2-42e4-995b-87045dfa165c",
        folio=4001,
        cancel_motivo="02",
        cancelled_at=cancelled_at,
    )

    result = await get_invoice_history_by_trip_endpoint(
        trip_id=TRIP_ID, uow_factory=_uow_factory([invoice])
    )

    assert len(result.invoices) == 1
    item = result.invoices[0]
    assert item.status == "canceled"
    assert item.cancel_motivo == "02"
    assert item.cancelled_at == cancelled_at
    assert item.pdf_url == "/v1/cfdi/93fafe6c-5bd2-42e4-995b-87045dfa165c/pdf"
    assert item.xml_url == "/v1/cfdi/93fafe6c-5bd2-42e4-995b-87045dfa165c/xml"


async def test_history_omits_urls_when_no_cfdi_uuid() -> None:
    invoice = _invoice(InvoiceStatus.failed, cfdi_uuid=None, folio=None)

    result = await get_invoice_history_by_trip_endpoint(
        trip_id=TRIP_ID, uow_factory=_uow_factory([invoice])
    )

    item = result.invoices[0]
    assert item.pdf_url is None
    assert item.xml_url is None


async def test_history_only_returns_invoices_for_requested_trip() -> None:
    other_trip_invoice = _invoice(InvoiceStatus.issued, cfdi_uuid="uuid-other", folio=1)
    other_trip_invoice.trip_id = 999
    this_trip_invoice = _invoice(InvoiceStatus.issued, cfdi_uuid="uuid-mine", folio=2)

    result = await get_invoice_history_by_trip_endpoint(
        trip_id=TRIP_ID, uow_factory=_uow_factory([other_trip_invoice, this_trip_invoice])
    )

    assert len(result.invoices) == 1
    assert result.invoices[0].cfdi_uuid == "uuid-mine"
