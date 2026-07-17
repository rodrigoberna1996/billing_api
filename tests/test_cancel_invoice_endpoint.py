"""Pruebas de las reglas de negocio del endpoint PUT /v1/cfdi/{cfdi_uuid}/cancel.

Se llama directamente a la función del router (sin arrancar FastAPI/TestClient),
inyectando fakes para uow_factory / facturalo_client / logistics_client, ya que
los `Depends(...)` son solo valores por defecto que se sobreescriben al pasar
los kwargs explícitamente.
"""
from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from app.domain.entities import Address, Invoice, Money, Party
from app.domain.enums import ComplementType, InvoiceStatus, InvoiceType
from app.interfaces.api.routers.carta_porte import cancel_invoice_endpoint

CFDI_UUID = "11111111-1111-1111-1111-111111111111"


def _invoice(
    status_: InvoiceStatus = InvoiceStatus.issued,
    form_snapshot: dict | None = None,
) -> Invoice:
    return Invoice(
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
        cfdi_uuid=CFDI_UUID,
        serie="CCP",
        folio=4001,
        trip_id=712,
        form_snapshot=form_snapshot,
    )


class _FakeInvoiceRepo:
    def __init__(self, invoice: Invoice | None) -> None:
        self._invoice = invoice
        self.updated: Invoice | None = None

    async def get_by_cfdi_uuid(self, cfdi_uuid: str) -> Invoice | None:
        return self._invoice

    async def update(self, invoice: Invoice) -> Invoice:
        self.updated = invoice
        return invoice


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

    factory.repo = repo  # type: ignore[attr-defined]
    return factory


class _FakeFacturaloClient:
    def __init__(self, response: dict | None = None) -> None:
        self.response = response or {"code": "201", "message": "UUID Cancelado exitosamente."}
        self.calls: list[dict] = []

    async def cancel_invoice(self, **kwargs: Any) -> dict:
        self.calls.append(kwargs)
        return self.response


class _FakeLogisticsClient:
    def __init__(self) -> None:
        self.notified: list[dict] = []

    async def notify_cfdi_cancelled(
        self,
        trip_id: int,
        cfdi_uuid: str,
        motivo: str | None = None,
        cancelled_at: Any | None = None,
    ) -> None:
        self.notified.append(
            {
                "trip_id": trip_id,
                "cfdi_uuid": cfdi_uuid,
                "motivo": motivo,
                "cancelled_at": cancelled_at,
            }
        )


async def test_cancel_rejects_invalid_motivo() -> None:
    uow_factory = _uow_factory(_invoice())
    with pytest.raises(HTTPException) as exc_info:
        await cancel_invoice_endpoint(
            cfdi_uuid=CFDI_UUID,
            motivo="99",
            folio_sustitucion="",
            uow_factory=uow_factory,
            facturalo_client=_FakeFacturaloClient(),
            logistics_client=_FakeLogisticsClient(),
        )
    assert exc_info.value.status_code == 400


async def test_cancel_requires_folio_sustitucion_for_motivo_01() -> None:
    uow_factory = _uow_factory(_invoice())
    with pytest.raises(HTTPException) as exc_info:
        await cancel_invoice_endpoint(
            cfdi_uuid=CFDI_UUID,
            motivo="01",
            folio_sustitucion="",
            uow_factory=uow_factory,
            facturalo_client=_FakeFacturaloClient(),
            logistics_client=_FakeLogisticsClient(),
        )
    assert exc_info.value.status_code == 400


async def test_cancel_returns_404_when_invoice_not_found() -> None:
    uow_factory = _uow_factory(None)
    with pytest.raises(HTTPException) as exc_info:
        await cancel_invoice_endpoint(
            cfdi_uuid=CFDI_UUID,
            motivo="02",
            folio_sustitucion="",
            uow_factory=uow_factory,
            facturalo_client=_FakeFacturaloClient(),
            logistics_client=_FakeLogisticsClient(),
        )
    assert exc_info.value.status_code == 404


async def test_cancel_is_idempotent_when_already_canceled() -> None:
    uow_factory = _uow_factory(_invoice(status_=InvoiceStatus.canceled))
    facturalo_client = _FakeFacturaloClient()

    result = await cancel_invoice_endpoint(
        cfdi_uuid=CFDI_UUID,
        motivo="02",
        folio_sustitucion="",
        uow_factory=uow_factory,
        facturalo_client=facturalo_client,
        logistics_client=_FakeLogisticsClient(),
    )

    assert result["status"] == "canceled"
    assert facturalo_client.calls == []  # no debe volver a llamar al PAC


async def test_cancel_rejects_when_invoice_not_issued() -> None:
    uow_factory = _uow_factory(_invoice(status_=InvoiceStatus.pending))
    with pytest.raises(HTTPException) as exc_info:
        await cancel_invoice_endpoint(
            cfdi_uuid=CFDI_UUID,
            motivo="02",
            folio_sustitucion="",
            uow_factory=uow_factory,
            facturalo_client=_FakeFacturaloClient(),
            logistics_client=_FakeLogisticsClient(),
        )
    assert exc_info.value.status_code == 409


async def test_cancel_success_updates_status_resolves_emisor_and_notifies_logistics() -> None:
    form_snapshot = {"Comprobante": {"Emisor": {"Rfc": "ALO161103C77"}}}
    invoice = _invoice(form_snapshot=form_snapshot)
    uow_factory = _uow_factory(invoice)
    facturalo_client = _FakeFacturaloClient()
    logistics_client = _FakeLogisticsClient()

    result = await cancel_invoice_endpoint(
        cfdi_uuid=CFDI_UUID,
        motivo="02",
        folio_sustitucion="",
        uow_factory=uow_factory,
        facturalo_client=facturalo_client,
        logistics_client=logistics_client,
    )

    assert result["status"] == "canceled"
    assert facturalo_client.calls[0]["rfc_emisor"] == "ALO161103C77"
    assert uow_factory.repo.updated.status == InvoiceStatus.canceled
    assert uow_factory.repo.updated.cancel_motivo == "02"
    assert len(logistics_client.notified) == 1
    assert logistics_client.notified[0]["trip_id"] == 712
    assert logistics_client.notified[0]["cfdi_uuid"] == CFDI_UUID
    assert logistics_client.notified[0]["motivo"] == "02"
    assert logistics_client.notified[0]["cancelled_at"] is not None
