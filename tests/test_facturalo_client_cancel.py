"""Pruebas del cliente FacturaloPlus para la operación de cancelación (cancelar2)."""
from __future__ import annotations

from typing import Any

import pytest

from app.infrastructure.http.facturalo_client import FacturaloPlusClient


def _client() -> FacturaloPlusClient:
    return FacturaloPlusClient(
        base_url="https://dev.facturaloplus.com",
        api_key="fake-api-key",
        key_pem="-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----",
        cer_pem="-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----",
        csd_key_b64="csd-key-b64",
        csd_cer_b64="csd-cer-b64",
        csd_password="s3cr3t",
        emisor_rfc="ENV010101ENV",
    )


@pytest.mark.asyncio
async def test_cancel_invoice_sends_folio_sustitucion_and_rfc_emisor_override(monkeypatch) -> None:
    client = _client()
    captured: dict[str, Any] = {}

    async def fake_post_form(
        url: str, data: dict, success_codes: frozenset[str] | None = None
    ) -> dict:
        captured["url"] = url
        captured["data"] = data
        captured["success_codes"] = success_codes
        return {"code": "201", "message": "UUID Cancelado exitosamente."}

    monkeypatch.setattr(client, "_post_form", fake_post_form)

    await client.cancel_invoice(
        cfdi_uuid="11111111-1111-1111-1111-111111111111",
        rfc_receptor="XAXX010101000",
        total="116.00",
        motivo="01",
        rfc_emisor="ALO161103C77",
        folio_sustitucion="22222222-2222-2222-2222-222222222222",
    )

    assert captured["url"].endswith("/api/rest/servicio/cancelar2")
    assert captured["data"]["rfcEmisor"] == "ALO161103C77"
    assert captured["data"]["folioSustitucion"] == "22222222-2222-2222-2222-222222222222"
    assert captured["data"]["motivo"] == "01"
    # Cancelación usa códigos de éxito 201/202, no 200 (ver Guía REST FacturaloPlus §5.2).
    assert captured["success_codes"] == frozenset({"201", "202"})


@pytest.mark.asyncio
async def test_cancel_invoice_falls_back_to_configured_emisor_rfc(monkeypatch) -> None:
    client = _client()
    captured: dict[str, Any] = {}

    async def fake_post_form(
        url: str, data: dict, success_codes: frozenset[str] | None = None
    ) -> dict:
        captured["data"] = data
        return {"code": "201", "message": "UUID Cancelado exitosamente."}

    monkeypatch.setattr(client, "_post_form", fake_post_form)

    await client.cancel_invoice(cfdi_uuid="uuid", motivo="02")

    assert captured["data"]["rfcEmisor"] == "ENV010101ENV"
    assert captured["data"]["folioSustitucion"] == ""


def test_cancel_invoice_code_201_is_treated_as_success() -> None:
    """code=201 ('UUID Cancelado exitosamente') no debe lanzar ExternalServiceError.

    Antes de este fix, _parse_response solo aceptaba code == '200', por lo que
    una cancelación real y exitosa (documentada como 201) se clasificaba como
    error y el endpoint devolvía 400 al frontend con un toast de error.
    """
    client = _client()
    response = client._parse_response(
        _FakeHttpxResponse({"code": "201", "message": "UUID Cancelado exitosamente."}),
        success_codes=frozenset({"201", "202"}),
    )
    assert response["message"] == "UUID Cancelado exitosamente."


def test_cancel_invoice_code_202_previously_cancelled_is_treated_as_success() -> None:
    client = _client()
    response = client._parse_response(
        _FakeHttpxResponse({"code": "202", "message": "UUID Previamente cancelado."}),
        success_codes=frozenset({"201", "202"}),
    )
    assert response["message"] == "UUID Previamente cancelado."


def test_cancel_invoice_code_200_is_not_a_valid_cancel_success() -> None:
    """200 es el código de éxito de timbrado, no de cancelar2; no debe aceptarse aquí."""
    from app.core.exceptions import ExternalServiceError

    client = _client()
    with pytest.raises(ExternalServiceError):
        client._parse_response(
            _FakeHttpxResponse({"code": "200", "message": "Solicitud procesada con éxito"}),
            success_codes=frozenset({"201", "202"}),
        )


class _FakeHttpxResponse:
    """Doble mínimo de httpx.Response para probar _parse_response sin red."""

    def __init__(self, body: dict, status_code: int = 200) -> None:
        self._body = body
        self.status_code = status_code
        self.text = str(body)

    def json(self) -> dict:
        return self._body
