"""Utilidades para respuestas de error estructuradas hacia el cliente."""
from __future__ import annotations

import re
from typing import Any

from app.application.services.carta_porte_validation import ValidationIssue
from app.core.exceptions import ExternalServiceError

_PAC_CODE_RE = re.compile(r"\[([A-Z0-9]+)\]:\s*(.+)", re.DOTALL)


def _hint_for_sat_code(code: str) -> str | None:
    hints: dict[str, str] = {
        "CP104": "Use moneda MXN para facturas de ingreso; XXX solo aplica a traslados.",
        "CP107": "En traslado el receptor debe ser el mismo RFC que el emisor.",
        "CP115": 'El complemento debe ser Carta Porte versión 3.1.',
        "CP147": "Revise que código postal, estado, municipio y colonia correspondan al catálogo SAT.",
        "CP184": "Agregue datos del remolque o cambie la configuración vehicular a una sin remolque (ej. C2).",
        "CFDI40130": "Factura a público en general: el sistema agrega InformacionGlobal automáticamente.",
        "CFDI40147": "El CP fiscal del receptor debe coincidir con el registrado en el SAT o con LugarExpedicion si usa XAXX.",
        "CFDI40148": "El nombre y CP del receptor deben coincidir con los datos del RFC en el SAT.",
        "500": "Error interno del PAC. Verifique CSD (keyPEM/cerPEM) y que estén vigentes.",
    }
    return hints.get(code)


def validation_issues_to_detail(issues: list[ValidationIssue]) -> dict[str, Any]:
    return {
        "message": "Los datos enviados no cumplen las validaciones requeridas para timbrar.",
        "type": "validation_error",
        "code": issues[0].code if issues else None,
        "errors": [
            {"field": i.field, "code": i.code, "message": i.message}
            for i in issues
        ],
        "hint": issues[0].message if len(issues) == 1 else "Corrija los campos indicados en errors.",
    }


def external_service_error_to_detail(error: ExternalServiceError) -> dict[str, Any]:
    code = getattr(error, "code", None)
    message = str(error)
    sat_message = message

    if not code:
        match = _PAC_CODE_RE.search(message)
        if match:
            code = match.group(1)
            sat_message = match.group(2).strip()
        elif message.startswith("FacturaloPlus "):
            parts = message.replace("FacturaloPlus ", "", 1)
            if parts.startswith("["):
                end = parts.find("]")
                if end > 0:
                    code = parts[1:end]
                    sat_message = parts[end + 1 :].lstrip(": ")

    hint = _hint_for_sat_code(code) if code else None
    if not hint:
        if code and code.startswith("CP"):
            hint = "Revise los datos del complemento Carta Porte según el mensaje del SAT."
        elif code and code.startswith("CFDI"):
            hint = "Revise los datos fiscales del emisor/receptor y totales del comprobante."
        else:
            hint = "Si el error persiste, contacte soporte con el código y mensaje."

    return {
        "message": sat_message,
        "type": "sat_error" if code and (code.startswith("CP") or code.startswith("CFDI")) else "pac_error",
        "code": code,
        "errors": [
            {
                "field": None,
                "code": code,
                "message": sat_message,
            }
        ],
        "hint": hint,
    }


def pydantic_errors_to_detail(errors: list[dict[str, Any]]) -> dict[str, Any]:
    formatted = []
    for err in errors:
        loc = ".".join(str(x) for x in err.get("loc", []) if x != "body")
        formatted.append({
            "field": loc or "body",
            "code": err.get("type", "validation"),
            "message": err.get("msg", "Valor inválido"),
        })
    return {
        "message": "El formato del JSON enviado es inválido.",
        "type": "schema_error",
        "code": "422",
        "errors": formatted,
        "hint": "Verifique que el payload coincida con el esquema esperado (emisor, receptor, factura).",
    }
