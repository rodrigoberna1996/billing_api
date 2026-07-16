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

    async def fake_post_form(url: str, data: dict) -> dict:
        captured["url"] = url
        captured["data"] = data
        return {"code": "200", "message": "Cancelado exitosamente"}

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


@pytest.mark.asyncio
async def test_cancel_invoice_falls_back_to_configured_emisor_rfc(monkeypatch) -> None:
    client = _client()
    captured: dict[str, Any] = {}

    async def fake_post_form(url: str, data: dict) -> dict:
        captured["data"] = data
        return {"code": "200", "message": "Cancelado exitosamente"}

    monkeypatch.setattr(client, "_post_form", fake_post_form)

    await client.cancel_invoice(cfdi_uuid="uuid", motivo="02")

    assert captured["data"]["rfcEmisor"] == "ENV010101ENV"
    assert captured["data"]["folioSustitucion"] == ""
