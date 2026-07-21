"""Pruebas de liberación de folio cuando el timbrado falla."""
from __future__ import annotations

import pytest

from app.domain.entities import Address, Invoice, Money, Party
from app.domain.enums import ComplementType, InvoiceStatus, InvoiceType
from app.interfaces.api.routers.carta_porte import _timbrado_background
from app.core.exceptions import ExternalServiceError


def _pending_invoice(*, folio: int = 4005) -> Invoice:
    return Invoice(
        recipient=Party(
            legal_name="Cliente",
            rfc="XAXX010101000",
            tax_regime="616",
            email=None,
            address=Address(
                street="Calle 1",
                exterior_number="1",
                neighborhood="Centro",
                city="Puebla",
                state="PUE",
                country="MEX",
                zip_code="72000",
            ),
            id=__import__("uuid").uuid4(),
        ),
        type=InvoiceType.ingreso,
        complement=ComplementType.carta_porte,
        currency="MXN",
        subtotal=Money(amount=10.0),
        total=Money(amount=11.6),
        cfdi_use="S01",
        payment_form="03",
        payment_method="PUE",
        expedition_place="20000",
        status=InvoiceStatus.pending,
        serie="CCP",
        folio=folio,
    )


class _FakeInvoices:
    def __init__(self, invoice: Invoice) -> None:
        self.invoice = invoice
        self.updated: list[Invoice] = []
        self.release_calls: list[int] = []
        self.release_result = True

    async def get_by_id(self, invoice_id):
        return self.invoice if self.invoice.id == invoice_id else None

    async def update(self, invoice: Invoice) -> Invoice:
        self.updated.append(invoice)
        return invoice

    async def release_folio_if_latest(self, folio: int) -> bool:
        self.release_calls.append(folio)
        return self.release_result


class _FakeUow:
    def __init__(self, invoices: _FakeInvoices) -> None:
        self.invoices = invoices

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None


class _FakeFacturalo:
    async def create_carta_porte(self, payload: dict) -> dict:
        raise ExternalServiceError("PAC rechazó el CFDI", code="CP999")


class _FakeLogistics:
    async def notify_cfdi_issued(self, **kwargs):
        raise AssertionError("no debe notificarse logistics en fallo")


@pytest.mark.asyncio
async def test_timbrado_background_releases_folio_on_pac_error() -> None:
    invoice = _pending_invoice(folio=4005)
    invoices = _FakeInvoices(invoice)

    def uow_factory():
        return _FakeUow(invoices)

    await _timbrado_background(
        invoice_id=invoice.id,
        sat_payload={"Comprobante": {}},
        trip_id=722,
        uow_factory=uow_factory,
        facturalo_client=_FakeFacturalo(),
        logistics_client=_FakeLogistics(),
    )

    assert invoice.status == InvoiceStatus.failed
    assert invoice.folio is None
    assert invoice.serie is None
    assert invoices.release_calls == [4005]
    assert len(invoices.updated) == 1
