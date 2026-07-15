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


def test_build_uses_request_emisor_in_comprobante() -> None:
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
