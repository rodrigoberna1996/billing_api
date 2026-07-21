"""Verifica que el emisor recibido en el request (gestionado desde Mi cuenta en
adrh_logistics) tenga prioridad sobre FACTURALO_EMISOR_* del entorno, con
respaldo campo a campo cuando el request no envía `emisor` o viene incompleto.
"""
from app.application.dtos.facturify_format import FacturifyCartaPorteRequest
from app.infrastructure.mappers.facturalo_payload import FacturaloPayloadBuilder

_EXAMPLE = FacturifyCartaPorteRequest.model_config["json_schema_extra"]["examples"][0]


def _builder() -> FacturaloPayloadBuilder:
    return FacturaloPayloadBuilder(
        emisor_rfc="ENV010101ENV",
        emisor_nombre="EMPRESA DEL ENV",
        emisor_regimen="601",
        emisor_cp="00000",
    )


def test_resolve_emisor_prefers_request_over_env() -> None:
    request = FacturifyCartaPorteRequest.model_validate(
        {
            **_EXAMPLE,
            "emisor": {
                "rfc": "ALO161103C77",
                "razon_social": "ADRH LOGISTICS SA DE CV",
                "cp": "76800",
                "regimen_fiscal": "601",
            },
        }
    )
    rfc, nombre, regimen, cp = _builder().resolve_emisor(request)

    assert rfc == "ALO161103C77"
    assert nombre == "ADRH LOGISTICS SA DE CV"
    assert regimen == "601"
    assert cp == "76800"


def test_resolve_emisor_falls_back_to_env_when_missing() -> None:
    request = FacturifyCartaPorteRequest.model_validate(_EXAMPLE)
    rfc, nombre, regimen, cp = _builder().resolve_emisor(request)

    assert rfc == "ENV010101ENV"
    assert nombre == "EMPRESA DEL ENV"
    assert regimen == "601"
    assert cp == "00000"


def test_resolve_emisor_falls_back_per_field() -> None:
    request = FacturifyCartaPorteRequest.model_validate(
        {
            **_EXAMPLE,
            "emisor": {"rfc": "ALO161103C77"},
        }
    )
    rfc, nombre, regimen, cp = _builder().resolve_emisor(request)

    assert rfc == "ALO161103C77"
    assert nombre == "EMPRESA DEL ENV"
    assert regimen == "601"
    assert cp == "00000"


def test_build_campos_pdf_includes_emisor_contacto() -> None:
    """Dirección/teléfono/correo del emisor van a CamposPDF (representación impresa)."""
    request = FacturifyCartaPorteRequest.model_validate(
        {
            **_EXAMPLE,
            "emisor": {
                "rfc": "ALO161103C77",
                "razon_social": "ADRH LOGISTICS SA DE CV",
                "cp": "76800",
                "regimen_fiscal": "601",
                "direccion": "Av. Industria 123, Col. Centro, Querétaro, Qro.",
                "telefono": "4421234567",
                "correo": "facturacion@adrh.mx",
            },
        }
    )
    payload = _builder().build(request)
    campos = payload["CamposPDF"]

    assert campos["calleEmisor"] == "Av. Industria 123, Col. Centro, Querétaro, Qro."
    assert campos["codigoPostalEmisor"] == "76800"
    assert campos["telefonoEmisor"] == "4421234567"
    assert campos["emailEmisor"] == "facturacion@adrh.mx"
    assert campos["correoEmisor"] == "facturacion@adrh.mx"

    request = FacturifyCartaPorteRequest.model_validate(
        {
            **_EXAMPLE,
            "emisor": {
                "rfc": "ALO161103C77",
                "razon_social": "ADRH LOGISTICS SA DE CV",
                "cp": "76800",
                "regimen_fiscal": "624",
            },
        }
    )
    payload = _builder().build(request)

    comprobante = payload["Comprobante"]
    assert comprobante["Emisor"]["Rfc"] == "ALO161103C77"
    assert comprobante["Emisor"]["Nombre"] == "ADRH LOGISTICS SA DE CV"
    assert comprobante["Emisor"]["RegimenFiscal"] == "624"
    assert comprobante["LugarExpedicion"] == "76800"


def test_build_ignores_serie_folio_from_request() -> None:
    """Serie/Folio ya no se toman del formulario: los asigna billing_api

    (invoices_folio_seq) tras crear la factura, para garantizar un folio
    consecutivo único y evitar condiciones de carrera.
    """
    request = FacturifyCartaPorteRequest.model_validate(
        {**_EXAMPLE, "factura": {**_EXAMPLE["factura"], "serie": "CPT", "folio": "999"}}
    )
    payload = _builder().build(request)

    comprobante = payload["Comprobante"]
    assert "Serie" not in comprobante
    assert "Folio" not in comprobante
