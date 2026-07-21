"""Pruebas de GET /v1/cfdi/by-receptor/{rfc}/last-form."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.domain.entities import Address, Invoice, Money, Party
from app.domain.enums import ComplementType, InvoiceStatus, InvoiceType
from app.interfaces.api.routers.carta_porte import get_last_form_by_receptor_endpoint

RFC = "XAXX010101000"
UI_DRAFT = {
    "schemaVersion": 1,
    "emisorUuid": "e1",
    "receptorUuid": "42",
    "metodoPago": "PPD",
    "formaPago": "99",
    "serie": "CCP",
    "cantidadConcepto": 1,
    "claveProductoServicio": "78101800",
    "claveUnidadMedida": "E48",
    "descripcionConcepto": "Flete",
    "objetoImp": "02",
    "ubicaciones": [],
    "mercancias": [],
    "pesoNetoTotal": 0,
    "pesoBrutoTotal": 0,
    "unidadPeso": "KGM",
    "metodoMercancias": "manual",
}


def _invoice(*, request_snapshot: dict | None) -> Invoice:
    return Invoice(
        id=uuid4(),
        recipient=Party(
            legal_name="Cliente de prueba",
            rfc=RFC,
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
        status=InvoiceStatus.issued,
        request_snapshot=request_snapshot,
    )


class _FakeInvoiceRepo:
    def __init__(self, invoice: Invoice | None) -> None:
        self._invoice = invoice
        self.last_rfc: str | None = None

    async def get_last_issued_with_request_snapshot_by_rfc(self, rfc: str) -> Invoice | None:
        self.last_rfc = rfc
        return self._invoice


class _FakeUow:
    def __init__(self, repo: _FakeInvoiceRepo) -> None:
        self.invoices = repo

    async def __aenter__(self) -> "_FakeUow":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None


def _uow_factory(invoice: Invoice | None):
    repo = _FakeInvoiceRepo(invoice)

    def factory() -> _FakeUow:
        return _FakeUow(repo)

    return factory, repo


async def test_last_form_returns_request_snapshot() -> None:
    invoice = _invoice(request_snapshot=UI_DRAFT)
    factory, repo = _uow_factory(invoice)

    result = await get_last_form_by_receptor_endpoint(
        rfc="  xaxx010101000  ",
        uow_factory=factory,
    )

    assert repo.last_rfc == RFC
    assert result.invoice_id == invoice.id
    assert result.payload == UI_DRAFT


async def test_last_form_404_when_missing() -> None:
    factory, _ = _uow_factory(None)

    with pytest.raises(HTTPException) as exc:
        await get_last_form_by_receptor_endpoint(rfc=RFC, uow_factory=factory)

    assert exc.value.status_code == 404


async def test_last_form_400_when_rfc_empty() -> None:
    factory, _ = _uow_factory(None)

    with pytest.raises(HTTPException) as exc:
        await get_last_form_by_receptor_endpoint(rfc="   ", uow_factory=factory)

    assert exc.value.status_code == 400
