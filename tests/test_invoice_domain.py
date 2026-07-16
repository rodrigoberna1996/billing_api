"""Pruebas de la entidad de dominio Invoice: transiciones de estatus."""
from __future__ import annotations

from app.domain.entities import Address, Invoice, Money, Party
from app.domain.enums import ComplementType, InvoiceStatus, InvoiceType


def _invoice() -> Invoice:
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
        status=InvoiceStatus.issued,
        cfdi_uuid="11111111-1111-1111-1111-111111111111",
        serie="CCP",
        folio=4001,
    )


def test_mark_canceled_sets_status_and_metadata() -> None:
    invoice = _invoice()
    response = {"code": "200", "message": "Cancelado exitosamente"}

    invoice.mark_canceled(motivo="02", response=response)

    assert invoice.status == InvoiceStatus.canceled
    assert invoice.cancel_motivo == "02"
    assert invoice.cancel_response == response
    assert invoice.cancelled_at is not None


def test_mark_canceled_stores_folio_sustitucion_in_response() -> None:
    invoice = _invoice()
    response = {"code": "200", "message": "Cancelado exitosamente"}
    sustitucion_uuid = "22222222-2222-2222-2222-222222222222"

    invoice.mark_canceled(motivo="01", response=response, folio_sustitucion=sustitucion_uuid)

    assert invoice.cancel_response["folio_sustitucion"] == sustitucion_uuid
