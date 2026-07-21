"""Builder que transforma FacturifyCartaPorteRequest al JSON SAT-nativo para FacturaloPlus."""
from __future__ import annotations

import base64
import logging
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from app.application.dtos.facturify_format import (
    CartaPorteComplementoDTO,
    ConceptoDTO,
    FacturifyCartaPorteRequest,
    MercanciaDTO,
    UbicacionDTO,
)

logger = logging.getLogger(__name__)

# app/infrastructure/mappers/ → raíz del repositorio
_PROJECT_ROOT = Path(__file__).resolve().parents[3]

RFC_PUBLICO_GENERAL = "XAXX010101000"
NOMBRE_PUBLICO_GENERAL = "PUBLICO EN GENERAL"

_TIPO_COMPROBANTE_MAP = {
    "ingreso": "I",
    "traslado": "T",
    "egreso": "E",
    "pago": "P",
    "nomina": "N",
}

_UNIT_DESCRIPTION_MAP: dict[str, str] = {
    "E48": "SERVICIO",
    "KGM": "KILOGRAMO",
    "H87": "PIEZA",
    "XPK": "PAQUETE",
    "ACT": "ACTIVIDAD",
    "LTR": "LITRO",
    "MTR": "METRO",
    "TON": "TONELADA",
}


def _fmt(value: float | int, decimals: int = 2) -> str:
    return f"{value:.{decimals}f}"


def _fmt_tasa(value: float) -> str:
    return f"{value:.6f}"


def _normalize_fecha(fecha: str) -> str:
    """Convierte '2026-01-21 15:58:20' o '2026-01-21T15:58:20' al formato SAT con T."""
    return fecha.strip().replace(" ", "T")


def _parse_fecha(fecha: str) -> datetime:
    return datetime.fromisoformat(_normalize_fecha(fecha))


@lru_cache(maxsize=4)
def load_logo_b64(path: str) -> str:
    """Lee un archivo de logo y lo convierte a base64 para el campo `logo` de FacturaloPlus.

    `path` puede ser absoluta o relativa a la raíz del repositorio. Si el archivo no
    existe, retorna cadena vacía (el PDF se genera sin logo).
    """
    if not path or not path.strip():
        return ""
    logo_path = Path(path.strip())
    if not logo_path.is_absolute():
        logo_path = _PROJECT_ROOT / logo_path
    if not logo_path.is_file():
        logger.warning("Logo no encontrado en %s; el PDF se generará sin logo", logo_path)
        return ""
    return base64.b64encode(logo_path.read_bytes()).decode("ascii")


class FacturaloPayloadBuilder:
    """Construye el payload JSON SAT-nativo para FacturaloPlus a partir del DTO de entrada."""

    def __init__(
        self,
        emisor_rfc: str,
        emisor_nombre: str,
        emisor_regimen: str,
        emisor_cp: str,
        csd_serial: str = "",
        logo_path: str = "",
    ) -> None:
        self._emisor_rfc = emisor_rfc
        self._emisor_nombre = emisor_nombre
        self._emisor_regimen = emisor_regimen
        self._emisor_cp = emisor_cp
        self._csd_serial = csd_serial
        self._logo_b64 = load_logo_b64(logo_path) if logo_path else ""

    def resolve_emisor(self, request: FacturifyCartaPorteRequest) -> tuple[str, str, str, str]:
        """Resuelve los datos del emisor: (rfc, nombre, regimen, cp).

        Prioriza el emisor recibido en el request (gestionado desde el módulo
        "Mi cuenta" en adrh_logistics) y usa FACTURALO_EMISOR_* como respaldo
        por cada campo que falte, para no romper otros clientes que aún no
        envíen `emisor` en el payload.
        """
        emisor = request.emisor
        rfc = (emisor.rfc if emisor else None) or self._emisor_rfc
        nombre = (emisor.razon_social if emisor else None) or self._emisor_nombre
        regimen = (emisor.regimen_fiscal if emisor else None) or self._emisor_regimen
        cp = (emisor.cp if emisor else None) or self._emisor_cp
        return (
            (rfc or "").strip(),
            (nombre or "").strip(),
            (regimen or "").strip(),
            (cp or "").strip(),
        )

    def build(self, request: FacturifyCartaPorteRequest) -> dict:
        """Retorna el dict listo para ser serializado y enviado a timbrarJSON2/3."""
        factura = request.factura
        receptor = request.receptor

        emisor_rfc, emisor_nombre, emisor_regimen, lugar_expedicion = self.resolve_emisor(request)
        tipo_comprobante = _TIPO_COMPROBANTE_MAP.get(factura.tipo, "I")

        comprobante: dict = {
            "Version": "4.0",
            "Fecha": _normalize_fecha(factura.fecha),
            "TipoDeComprobante": tipo_comprobante,
            "Exportacion": factura.exportacion,
            "Moneda": factura.moneda,
            "SubTotal": _fmt(factura.subtotal),
            "Total": _fmt(factura.total),
            "LugarExpedicion": lugar_expedicion,
            **({"NoCertificado": self._csd_serial} if self._csd_serial else {}),
            "Emisor": {
                "Rfc": emisor_rfc,
                "Nombre": emisor_nombre,
                "RegimenFiscal": emisor_regimen,
            },
            "Receptor": self._build_receptor(
                factura,
                receptor,
                emisor_rfc=emisor_rfc,
                emisor_nombre=emisor_nombre,
                emisor_regimen=emisor_regimen,
                lugar_expedicion=lugar_expedicion,
            ),
            "Conceptos": [self._build_concepto(c) for c in factura.conceptos],
        }

        if factura.moneda != "XXX":
            comprobante["MetodoPago"] = factura.metodo_de_pago
            comprobante["FormaPago"] = factura.forma_de_pago
            comprobante["TipoCambio"] = factura.tipo_de_cambio

        impuestos_comprobante = self._build_impuestos_comprobante(factura.conceptos)
        if impuestos_comprobante:
            comprobante["Impuestos"] = impuestos_comprobante

        receptor_rfc = comprobante["Receptor"]["Rfc"]
        if tipo_comprobante == "I" and receptor_rfc == RFC_PUBLICO_GENERAL:
            comprobante["InformacionGlobal"] = self._build_informacion_global(factura.fecha)

        carta_porte = factura.Complemento.CartaPorte
        comprobante["Complemento"] = [{"CartaPorte31": self._build_carta_porte(carta_porte)}]

        return {
            "Comprobante": comprobante,
            "CamposPDF": self._build_campos_pdf(
                factura,
                carta_porte,
                emisor=request.emisor,
                emisor_cp=lugar_expedicion,
            ),
            "logo": self._logo_b64,
        }

    def _build_informacion_global(self, fecha: str) -> dict:
        dt = _parse_fecha(fecha)
        return {
            "Periodicidad": "04",
            "Meses": f"{dt.month:02d}",
            "Año": str(dt.year),
        }

    def _build_receptor(
        self,
        factura,
        receptor,
        *,
        emisor_rfc: str,
        emisor_nombre: str,
        emisor_regimen: str,
        lugar_expedicion: str,
    ) -> dict:
        if factura.tipo == "traslado":
            rfc = emisor_rfc
            nombre = emisor_nombre
            cp = lugar_expedicion
            regimen = emisor_regimen
            uso_cfdi = "S01"
        else:
            rfc = (receptor.rfc or "").strip() or RFC_PUBLICO_GENERAL
            nombre = (receptor.razon_social or "").strip() or NOMBRE_PUBLICO_GENERAL
            cp = (receptor.cp or "").strip() or lugar_expedicion
            if rfc == RFC_PUBLICO_GENERAL:
                cp = lugar_expedicion
            regimen = (receptor.regimen or "").strip() or "616"
            uso_cfdi = factura.uso_cfdi or "S01"

        return {
            "Rfc": rfc,
            "Nombre": nombre,
            "DomicilioFiscalReceptor": cp,
            "RegimenFiscalReceptor": regimen,
            "UsoCFDI": uso_cfdi,
        }

    def _build_concepto(self, c: ConceptoDTO) -> dict:
        unidad_desc = _UNIT_DESCRIPTION_MAP.get(c.clave_unidad_de_medida, c.clave_unidad_de_medida)
        concepto: dict = {
            "ClaveProdServ": c.clave_producto_servicio,
            "Cantidad": _fmt(c.cantidad, 0) if c.cantidad == int(c.cantidad) else _fmt(c.cantidad),
            "ClaveUnidad": c.clave_unidad_de_medida,
            "Unidad": unidad_desc,
            "Descripcion": c.descripcion,
            "ValorUnitario": _fmt(c.valor_unitario),
            "Importe": _fmt(c.total),
            "ObjetoImp": c.objeto_imp,
        }

        if c.impuestos:
            imp = self._build_impuestos_concepto(c.impuestos)
            if imp:
                concepto["Impuestos"] = imp

        return concepto

    def _build_impuestos_concepto(self, impuestos) -> dict:
        result: dict = {}

        if impuestos.traslados and impuestos.traslados.traslado:
            result["Traslados"] = [
                {
                    "Base": _fmt(t.base),
                    "Impuesto": t.impuesto,
                    "TipoFactor": t.tipoFactor,
                    "TasaOCuota": _fmt_tasa(t.tasaOCuota),
                    "Importe": _fmt(t.importe),
                }
                for t in impuestos.traslados.traslado
            ]

        if impuestos.retenciones and impuestos.retenciones.retencion:
            result["Retenciones"] = [
                {
                    "Base": _fmt(r.base),
                    "Impuesto": r.impuesto,
                    "TipoFactor": r.tipoFactor,
                    "TasaOCuota": _fmt_tasa(r.tasaOCuota),
                    "Importe": _fmt(r.importe),
                }
                for r in impuestos.retenciones.retencion
            ]

        return result

    def _build_impuestos_comprobante(self, conceptos: list[ConceptoDTO]) -> dict:
        total_traslados: dict[tuple, dict] = {}
        total_retenciones: dict[tuple, dict] = {}

        for c in conceptos:
            if not c.impuestos:
                continue
            if c.impuestos.traslados:
                for t in c.impuestos.traslados.traslado:
                    key = (t.impuesto, t.tipoFactor, _fmt_tasa(t.tasaOCuota))
                    if key in total_traslados:
                        total_traslados[key]["Base"] = _fmt(
                            float(total_traslados[key]["Base"]) + t.base
                        )
                        total_traslados[key]["Importe"] = _fmt(
                            float(total_traslados[key]["Importe"]) + t.importe
                        )
                    else:
                        total_traslados[key] = {
                            "Base": _fmt(t.base),
                            "Impuesto": t.impuesto,
                            "TipoFactor": t.tipoFactor,
                            "TasaOCuota": _fmt_tasa(t.tasaOCuota),
                            "Importe": _fmt(t.importe),
                        }
            if c.impuestos.retenciones:
                for r in c.impuestos.retenciones.retencion:
                    key = (r.impuesto, r.tipoFactor, _fmt_tasa(r.tasaOCuota))
                    if key in total_retenciones:
                        total_retenciones[key]["Base"] = _fmt(
                            float(total_retenciones[key]["Base"]) + r.base
                        )
                        total_retenciones[key]["Importe"] = _fmt(
                            float(total_retenciones[key]["Importe"]) + r.importe
                        )
                    else:
                        total_retenciones[key] = {
                            "Base": _fmt(r.base),
                            "Impuesto": r.impuesto,
                            "TipoFactor": r.tipoFactor,
                            "TasaOCuota": _fmt_tasa(r.tasaOCuota),
                            "Importe": _fmt(r.importe),
                        }

        if not total_traslados and not total_retenciones:
            return {}

        result: dict = {}

        if total_traslados:
            total_imp_traslados = sum(float(v["Importe"]) for v in total_traslados.values())
            result["TotalImpuestosTrasladados"] = _fmt(total_imp_traslados)
            result["Traslados"] = list(total_traslados.values())

        if total_retenciones:
            total_imp_retenciones = sum(float(v["Importe"]) for v in total_retenciones.values())
            result["TotalImpuestosRetenidos"] = _fmt(total_imp_retenciones)
            result["Retenciones"] = list(total_retenciones.values())

        return result

    def _build_carta_porte(self, cp: CartaPorteComplementoDTO) -> dict:
        carta: dict = {
            "Version": "3.1",
            "TranspInternac": cp.TranspInternac,
            "TotalDistRec": _fmt(cp.TotalDistRec),
            "Ubicaciones": {
                "Ubicacion": [self._build_ubicacion(u) for u in cp.Ubicaciones.Ubicacion]
            },
            "Mercancias": self._build_mercancias(cp),
            "FiguraTransporte": {
                "TiposFigura": [
                    self._build_figura(f)
                    for f in cp.FiguraTransporte.TiposFigura
                ]
            },
        }

        if cp.IdCCP:
            carta["IdCCP"] = cp.IdCCP

        return carta

    def _build_ubicacion(self, u: UbicacionDTO) -> dict:
        ubicacion: dict = {
            "TipoUbicacion": u.TipoUbicacion,
            "IDUbicacion": u.IDUbicacion,
            "RFCRemitenteDestinatario": u.RFCRemitenteDestinatario,
            "FechaHoraSalidaLlegada": _normalize_fecha(u.FechaHoraSalidaLlegada),
            "Domicilio": self._build_domicilio(u.Domicilio),
        }

        if u.NombreRemitenteDestinatario:
            ubicacion["NombreRemitenteDestinatario"] = u.NombreRemitenteDestinatario

        if u.TipoUbicacion == "Destino" and u.DistanciaRecorrida is not None:
            ubicacion["DistanciaRecorrida"] = _fmt(u.DistanciaRecorrida)

        return ubicacion

    def _build_domicilio(self, d) -> dict:
        dom: dict = {
            "Calle": d.Calle,
            "CodigoPostal": d.CodigoPostal,
            "Estado": d.Estado,
            "Pais": d.Pais,
        }
        optional_fields = [
            ("NumeroExterior", d.NumeroExterior),
            ("NumeroInterior", d.NumeroInterior),
            ("Colonia", d.Colonia),
            ("Localidad", d.Localidad),
            ("Referencia", d.Referencia),
            ("Municipio", d.Municipio),
        ]
        for key, val in optional_fields:
            if val and val.strip():
                dom[key] = val.strip()
        return dom

    def _build_mercancias(self, cp: CartaPorteComplementoDTO) -> dict:
        from decimal import Decimal
        m = cp.Mercancias
        # Sumar los pesos ya formateados (3 dec, tope SAT xs:decimal para PesoEnKg/PesoBrutoTotal/
        # PesoNetoTotal) con Decimal para imitar exactamente lo que hace el SAT al validar CP149:
        # sum(Mercancia.PesoEnKg) con precisión exacta.
        peso_bruto_calculado = sum(Decimal(_fmt(item.PesoEnKg, 3)) for item in m.Mercancia)
        mercancias: dict = {
            "PesoBrutoTotal": str(peso_bruto_calculado),
            "UnidadPeso": m.UnidadPeso,
            "NumTotalMercancias": str(m.NumTotalMercancias),
            "Mercancia": [self._build_mercancia(item) for item in m.Mercancia],
            "Autotransporte": self._build_autotransporte(m.Autotransporte),
        }
        if m.PesoNetoTotal and m.PesoNetoTotal > 0:
            mercancias["PesoNetoTotal"] = _fmt(m.PesoNetoTotal, 3)
        return mercancias

    def _build_mercancia(self, item: MercanciaDTO) -> dict:
        mercancia: dict = {
            "BienesTransp": item.BienesTransp,
            "Descripcion": item.Descripcion,
            "Cantidad": _fmt(item.Cantidad, 0) if item.Cantidad == int(item.Cantidad) else _fmt(item.Cantidad),
            "ClaveUnidad": item.ClaveUnidad,
            "PesoEnKg": _fmt(item.PesoEnKg, 3),
        }

        # MaterialPeligroso solo se incluye cuando el producto es peligroso ("Sí").
        # Productos con "0" en la columna MaterialPeligroso del catálogo c_ClaveProdServCP
        # no deben llevar este atributo (ni siquiera como "No") — error CP155.
        es_peligroso = item.MaterialPeligroso and item.MaterialPeligroso.strip().lower() in ("sí", "si", "s")
        if es_peligroso:
            mercancia["MaterialPeligroso"] = "Sí"
            if item.CveMaterialPeligroso:
                mercancia["CveMaterialPeligroso"] = item.CveMaterialPeligroso
            if item.Embalaje:
                mercancia["Embalaje"] = item.Embalaje
            if item.DescripEmbalaje:
                mercancia["DescripEmbalaje"] = item.DescripEmbalaje

        if item.CantidadTransporta:
            mercancia["CantidadTransporta"] = [
                {
                    "Cantidad": _fmt(ct.Cantidad, 0) if ct.Cantidad == int(ct.Cantidad) else _fmt(ct.Cantidad),
                    "IDOrigen": ct.IDOrigen,
                    "IDDestino": ct.IDDestino,
                }
                for ct in item.CantidadTransporta
            ]

        return mercancia

    def _build_autotransporte(self, auto) -> dict:
        result: dict = {
            "PermSCT": auto.PermSCT,
            "NumPermisoSCT": auto.NumPermisoSCT,
            "IdentificacionVehicular": {
                "ConfigVehicular": auto.IdentificacionVehicular.ConfigVehicular,
                "PlacaVM": auto.IdentificacionVehicular.PlacaVM,
                "AnioModeloVM": auto.IdentificacionVehicular.AnioModeloVM,
                "PesoBrutoVehicular": auto.IdentificacionVehicular.PesoBrutoVehicular,
            },
            "Seguros": {
                "AseguraRespCivil": auto.Seguros.AseguraRespCivil,
                "PolizaRespCivil": auto.Seguros.PolizaRespCivil,
            },
        }

        if auto.Seguros.PrimaSeguro and auto.Seguros.PrimaSeguro.strip():
            result["Seguros"]["PrimaSeguro"] = auto.Seguros.PrimaSeguro.strip()

        if auto.Remolques and auto.Remolques.Remolque:
            result["Remolques"] = {
                "Remolque": [
                    {"SubTipoRem": r.SubTipoRem, "Placa": r.Placa}
                    for r in auto.Remolques.Remolque
                ]
            }

        return result

    def _build_figura(self, f) -> dict:
        figura: dict = {
            "TipoFigura": f.TipoFigura,
            "RFCFigura": f.RFCFigura,
            "NombreFigura": f.NombreFigura,
        }
        if f.NumLicencia:
            figura["NumLicencia"] = f.NumLicencia
        return figura

    def _build_campos_pdf(
        self,
        factura,
        cp: CartaPorteComplementoDTO,
        *,
        emisor=None,
        emisor_cp: str = "",
    ) -> dict:
        origen = next(
            (u for u in cp.Ubicaciones.Ubicacion if u.TipoUbicacion == "Origen"), None
        )
        destino = next(
            (u for u in cp.Ubicaciones.Ubicacion if u.TipoUbicacion == "Destino"), None
        )

        def _dir(u: UbicacionDTO | None) -> str:
            if not u:
                return ""
            d = u.Domicilio
            parts = [d.Calle]
            if d.NumeroExterior:
                parts.append(d.NumeroExterior)
            if d.Municipio:
                parts.append(d.Municipio)
            parts.append(d.Estado)
            return " ".join(p for p in parts if p)

        figura = (
            cp.FiguraTransporte.TiposFigura[0]
            if cp.FiguraTransporte.TiposFigura
            else None
        )
        auto = cp.Mercancias.Autotransporte

        # Dirección/contacto del emisor: texto libre desde Mi cuenta (empresa_fiscal).
        # FacturaloPlus los inserta en la plantilla PDF vía CamposPDF (no van al XML SAT).
        direccion = ((emisor.direccion if emisor else None) or "").strip()
        telefono = ((emisor.telefono if emisor else None) or "").strip()
        correo = ((emisor.correo if emisor else None) or "").strip()
        cp_emisor = (emisor_cp or "").strip()

        campos: dict = {
            "tipoComprobante": "CARTA PORTE",
            "Comentarios": "",
            "CartaPorte_Origen": _dir(origen),
            "CartaPorte_Destino": _dir(destino),
            "CartaPorte_Conductor": figura.NombreFigura if figura else "",
            "CartaPorte_Placas": auto.IdentificacionVehicular.PlacaVM,
            "CartaPorte_Vehiculo": (
                f"{auto.IdentificacionVehicular.ConfigVehicular} "
                f"{auto.IdentificacionVehicular.AnioModeloVM}"
            ),
            "CartaPorte_Kilometros": _fmt(cp.TotalDistRec),
            # Domicilio / contacto emisor (plantillas FacturaloPlus: *Emisor)
            "calleEmisor": direccion,
            "codigoPostalEmisor": cp_emisor,
            "telefonoEmisor": telefono,
            "emailEmisor": correo,
            "correoEmisor": correo,
        }
        return campos
