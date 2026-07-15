"""Validaciones de negocio y SAT previas al timbrado de Carta Porte."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.application.dtos.facturify_format import FacturifyCartaPorteRequest

RFC_PUBLICO_GENERAL = "XAXX010101000"
NOMBRE_PUBLICO_GENERAL = "PUBLICO EN GENERAL"

# c_ConfigAutotransporte: columna Remolque = 1 (obligatorio)
_CONFIG_REQUIERE_REMOLQUE = frozenset({
    "C2R2", "C2R3", "C3R2", "C3R3",
    "T2S2", "T2S3", "T3S2", "T3S3",
    "T2S2R2", "T2S2R3", "T2S3R2", "T2S3R3",
    "T3S2R2", "T3S2R3", "T3S3R2", "T3S3R3",
})

# Claves de servicio de transporte válidas para ingreso con Carta Porte (subset SAT)
_CLAVES_SERVICIO_TRANSPORTE = frozenset({
    "78101500", "78101501", "78101502", "78101503",
    "78101600", "78101601", "78101602", "78101603", "78101604",
    "78101700", "78101701", "78101702", "78101703", "78101704",
    "78101705", "78101706", "78101800", "78101801", "78101802",
    "78101803", "78101804", "78101806", "78101807",
    "78101900", "78101901", "78101902", "78101903", "78101904", "78101905",
    "78102200", "78102201", "78102203", "78102204", "78102205",
    "78121603", "78141500", "78141501", "84121806",
    "92121800", "92121801", "92121802",
})


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    code: str
    message: str


class CartaPorteValidationError(Exception):
    """Errores de validación previos al timbrado."""

    def __init__(self, issues: list[ValidationIssue]) -> None:
        self.issues = issues
        summary = issues[0].message if issues else "Datos inválidos para timbrado"
        super().__init__(summary)


def validate_carta_porte_request(
    request: FacturifyCartaPorteRequest,
    *,
    emisor_rfc_config: str = "",
    emisor_cp_config: str = "",
) -> list[ValidationIssue]:
    """Retorna lista de problemas; vacía si el request es válido.

    El emisor recibido en `request.emisor` (gestionado desde el módulo "Mi
    cuenta" en adrh_logistics) tiene prioridad sobre `emisor_rfc_config` /
    `emisor_cp_config`, que quedan como respaldo por variables de entorno.
    """
    issues: list[ValidationIssue] = []

    emisor_rfc = ((request.emisor.rfc if request.emisor else None) or emisor_rfc_config).strip()
    emisor_cp = ((request.emisor.cp if request.emisor else None) or emisor_cp_config).strip()
    receptor_rfc = (request.receptor.rfc or "").strip().upper()
    receptor_nombre = (request.receptor.razon_social or "").strip().upper()
    factura = request.factura
    tipo = factura.tipo
    cp = factura.Complemento.CartaPorte

    if not emisor_rfc:
        issues.append(ValidationIssue("emisor.rfc", "required", "El RFC del emisor es obligatorio."))
    if not emisor_cp:
        issues.append(ValidationIssue("emisor.cp", "required", "El código postal del emisor (lugar de expedición) es obligatorio."))
    if not receptor_rfc:
        issues.append(ValidationIssue("receptor.rfc", "required", "El RFC del receptor es obligatorio."))
    if not (request.receptor.razon_social or "").strip():
        issues.append(ValidationIssue("receptor.razon_social", "required", "La razón social del receptor es obligatoria."))

    # Tipo ingreso vs traslado
    if tipo == "ingreso":
        if factura.moneda == "XXX":
            issues.append(ValidationIssue(
                "factura.moneda", "CP104",
                "Para factura de ingreso la moneda no puede ser 'XXX'. Use MXN u otra moneda real.",
            ))
        if not factura.conceptos:
            issues.append(ValidationIssue("factura.conceptos", "required", "Debe incluir al menos un concepto."))
        for i, concepto in enumerate(factura.conceptos):
            if concepto.clave_producto_servicio not in _CLAVES_SERVICIO_TRANSPORTE:
                issues.append(ValidationIssue(
                    f"factura.conceptos[{i}].clave_producto_servicio",
                    "CP105",
                    f"La clave {concepto.clave_producto_servicio} no es una clave de servicio de transporte válida para ingreso con Carta Porte.",
                ))
        if receptor_rfc == RFC_PUBLICO_GENERAL:
            if emisor_cp and (request.receptor.cp or "").strip() and request.receptor.cp.strip() != emisor_cp:
                issues.append(ValidationIssue(
                    "receptor.cp", "CFDI40147",
                    "Con receptor XAXX010101000 el DomicilioFiscalReceptor debe coincidir con el LugarExpedicion del emisor.",
                ))
    elif tipo == "traslado":
        if factura.moneda != "XXX":
            issues.append(ValidationIssue(
                "factura.moneda", "CP103",
                "Para comprobante de traslado la moneda debe ser 'XXX'.",
            ))
        if emisor_rfc and receptor_rfc and receptor_rfc != emisor_rfc.upper():
            issues.append(ValidationIssue(
                "receptor.rfc", "CP107",
                "En traslado el RFC del receptor debe ser igual al RFC del emisor.",
            ))

    # Totales e impuestos
    if tipo == "ingreso" and factura.subtotal > 0:
        if factura.total < factura.subtotal:
            issues.append(ValidationIssue(
                "factura.total", "invalid_total",
                f"El total ({factura.total}) no puede ser menor al subtotal ({factura.subtotal}).",
            ))

        traslados_sum = 0.0
        retenciones_sum = 0.0
        for c in factura.conceptos:
            if not c.impuestos:
                continue
            if c.impuestos.traslados:
                traslados_sum += sum(t.importe for t in c.impuestos.traslados.traslado)
            if c.impuestos.retenciones:
                retenciones_sum += sum(r.importe for r in c.impuestos.retenciones.retencion)

        if traslados_sum or retenciones_sum:
            expected_total = round(factura.subtotal + traslados_sum - retenciones_sum, 2)
            if abs(factura.total - expected_total) > 0.02:
                issues.append(ValidationIssue(
                    "factura.total", "invalid_tax_total",
                    f"El total ({factura.total}) no coincide con subtotal + traslados - retenciones "
                    f"({expected_total}). Revise los importes de IVA/retenciones en conceptos.",
                ))

    # Carta Porte complemento
    if cp.Version != "3.1":
        issues.append(ValidationIssue(
            "factura.Complemento.CartaPorte.Version", "CP115",
            'La versión del complemento Carta Porte debe ser "3.1".',
        ))
    if not cp.IdCCP or not cp.IdCCP.strip():
        issues.append(ValidationIssue(
            "factura.Complemento.CartaPorte.IdCCP", "required",
            "El identificador IdCCP es obligatorio.",
        ))
    elif not re.match(r"^CCC[A-F0-9-]{31,}$", cp.IdCCP.strip(), re.IGNORECASE):
        issues.append(ValidationIssue(
            "factura.Complemento.CartaPorte.IdCCP", "invalid_format",
            "IdCCP debe iniciar con CCC seguido de un identificador único (formato UUID).",
        ))

    ubicaciones = cp.Ubicaciones.Ubicacion
    origenes = [u for u in ubicaciones if u.TipoUbicacion == "Origen"]
    destinos = [u for u in ubicaciones if u.TipoUbicacion == "Destino"]
    if not origenes:
        issues.append(ValidationIssue(
            "factura.Complemento.CartaPorte.Ubicaciones", "required",
            "Debe registrar al menos una ubicación de tipo Origen.",
        ))
    if not destinos:
        issues.append(ValidationIssue(
            "factura.Complemento.CartaPorte.Ubicaciones", "required",
            "Debe registrar al menos una ubicación de tipo Destino.",
        ))

    for idx, u in enumerate(ubicaciones):
        prefix = f"factura.Complemento.CartaPorte.Ubicaciones[{idx}]"
        if not u.RFCRemitenteDestinatario.strip():
            issues.append(ValidationIssue(f"{prefix}.RFCRemitenteDestinatario", "required", "RFC de remitente/destinatario obligatorio."))
        if not u.FechaHoraSalidaLlegada.strip():
            issues.append(ValidationIssue(f"{prefix}.FechaHoraSalidaLlegada", "required", "Fecha y hora de salida/llegada obligatoria."))
        dom = u.Domicilio
        dom_prefix = f"{prefix}.Domicilio"
        if not dom.CodigoPostal.strip():
            issues.append(ValidationIssue(f"{dom_prefix}.CodigoPostal", "required", "Código postal obligatorio en domicilio."))
        if not dom.Estado.strip():
            issues.append(ValidationIssue(f"{dom_prefix}.Estado", "required", "Estado obligatorio en domicilio (clave SAT de 3 caracteres)."))
        if not dom.Pais.strip():
            issues.append(ValidationIssue(f"{dom_prefix}.Pais", "required", "País obligatorio en domicilio."))
        if dom.Pais.strip().upper() == "MEX":
            if not dom.Municipio or not dom.Municipio.strip():
                issues.append(ValidationIssue(
                    f"{dom_prefix}.Municipio", "CP147",
                    "Municipio obligatorio para domicilios en México (debe corresponder al código postal en catálogo SAT).",
                ))
        if u.TipoUbicacion == "Destino" and (u.DistanciaRecorrida is None or u.DistanciaRecorrida < 0.01):
            issues.append(ValidationIssue(
                f"{prefix}.DistanciaRecorrida", "required",
                "La distancia recorrida es obligatoria en ubicaciones de tipo Destino (mínimo 0.01 km).",
            ))

    if not cp.Mercancias.Mercancia:
        issues.append(ValidationIssue(
            "factura.Complemento.CartaPorte.Mercancias.Mercancia", "required",
            "Debe registrar al menos una mercancía.",
        ))

    auto = cp.Mercancias.Autotransporte
    auto_prefix = "factura.Complemento.CartaPorte.Mercancias.Autotransporte"
    iv_prefix = f"{auto_prefix}.IdentificacionVehicular"
    seg_prefix = f"{auto_prefix}.Seguros"

    if not auto.PermSCT.strip():
        issues.append(ValidationIssue(f"{auto_prefix}.PermSCT", "required", "El permiso SCT es obligatorio."))
    if not auto.NumPermisoSCT.strip():
        issues.append(ValidationIssue(f"{auto_prefix}.NumPermisoSCT", "required", "El número de permiso SCT es obligatorio."))

    iv = auto.IdentificacionVehicular
    config = iv.ConfigVehicular.strip().upper()
    if not config:
        issues.append(ValidationIssue(f"{iv_prefix}.ConfigVehicular", "required", "La configuración vehicular es obligatoria."))
    if not iv.PlacaVM.strip():
        issues.append(ValidationIssue(f"{iv_prefix}.PlacaVM", "required", "Las placas del vehículo son obligatorias."))
    if not iv.AnioModeloVM.strip():
        issues.append(ValidationIssue(f"{iv_prefix}.AnioModeloVM", "required", "El año modelo del vehículo es obligatorio."))
    if not iv.PesoBrutoVehicular.strip():
        issues.append(ValidationIssue(
            f"{iv_prefix}.PesoBrutoVehicular",
            "required",
            "El peso bruto vehicular es obligatorio.",
        ))
    else:
        try:
            if float(iv.PesoBrutoVehicular) <= 0:
                issues.append(ValidationIssue(
                    f"{iv_prefix}.PesoBrutoVehicular",
                    "invalid_value",
                    "El peso bruto vehicular debe ser mayor a 0 toneladas.",
                ))
        except ValueError:
            issues.append(ValidationIssue(
                f"{iv_prefix}.PesoBrutoVehicular",
                "invalid_value",
                "El peso bruto vehicular debe ser numérico.",
            ))

    seg = auto.Seguros
    if not seg.AseguraRespCivil.strip():
        issues.append(ValidationIssue(f"{seg_prefix}.AseguraRespCivil", "required", "La aseguradora de responsabilidad civil es obligatoria."))
    if not seg.PolizaRespCivil.strip():
        issues.append(ValidationIssue(f"{seg_prefix}.PolizaRespCivil", "required", "La póliza de responsabilidad civil es obligatoria."))

    tiene_remolques = bool(auto.Remolques and auto.Remolques.Remolque)

    if config in _CONFIG_REQUIERE_REMOLQUE and not tiene_remolques:
        issues.append(ValidationIssue(
            f"{auto_prefix}.Remolques",
            "CP184",
            f"La configuración vehicular '{config}' requiere declarar al menos un remolque.",
        ))

    if tiene_remolques:
        for idx, rem in enumerate(auto.Remolques.Remolque):
            rem_prefix = f"{auto_prefix}.Remolques[{idx}]"
            if not rem.SubTipoRem.strip():
                issues.append(ValidationIssue(f"{rem_prefix}.SubTipoRem", "required", "El subtipo de remolque es obligatorio."))
            if not rem.Placa.strip():
                issues.append(ValidationIssue(f"{rem_prefix}.Placa", "required", "La placa del remolque es obligatoria."))

    destinos_con_distancia = [
        u for u in destinos
        if u.DistanciaRecorrida is not None and u.DistanciaRecorrida > 0
    ]
    if destinos_con_distancia:
        suma_distancias = round(sum(u.DistanciaRecorrida for u in destinos_con_distancia), 2)
        if abs(round(cp.TotalDistRec, 2) - suma_distancias) > 0.02:
            issues.append(ValidationIssue(
                "factura.Complemento.CartaPorte.TotalDistRec",
                "invalid_total_distance",
                f"TotalDistRec ({cp.TotalDistRec}) debe coincidir con la suma de DistanciaRecorrida "
                f"en destinos ({suma_distancias}).",
            ))

    if not cp.FiguraTransporte.TiposFigura:
        issues.append(ValidationIssue(
            "factura.Complemento.CartaPorte.FiguraTransporte", "required",
            "Debe registrar al menos una figura de transporte (conductor).",
        ))
    else:
        for idx, fig in enumerate(cp.FiguraTransporte.TiposFigura):
            if not fig.RFCFigura.strip():
                issues.append(ValidationIssue(
                    f"factura.Complemento.CartaPorte.FiguraTransporte[{idx}].RFCFigura",
                    "required", "RFC del conductor obligatorio.",
                ))
            if not fig.NombreFigura.strip():
                issues.append(ValidationIssue(
                    f"factura.Complemento.CartaPorte.FiguraTransporte[{idx}].NombreFigura",
                    "required", "Nombre del conductor obligatorio.",
                ))
            if not (fig.NumLicencia or "").strip():
                issues.append(ValidationIssue(
                    f"factura.Complemento.CartaPorte.FiguraTransporte[{idx}].NumLicencia",
                    "required", "Número de licencia del operador obligatorio.",
                ))

    return issues


def assert_valid_carta_porte_request(
    request: FacturifyCartaPorteRequest,
    *,
    emisor_rfc_config: str = "",
    emisor_cp_config: str = "",
) -> None:
    issues = validate_carta_porte_request(
        request,
        emisor_rfc_config=emisor_rfc_config,
        emisor_cp_config=emisor_cp_config,
    )
    if issues:
        raise CartaPorteValidationError(issues)
