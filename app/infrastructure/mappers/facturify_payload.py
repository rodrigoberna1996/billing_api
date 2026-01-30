"""Traduccion de entidades internas al payload esperado por Facturify."""
from __future__ import annotations

import uuid
from datetime import datetime

from app.domain.enums import ShipmentLocationType
from app.domain.entities import Invoice, InvoiceItem, Party, ShipmentLocation


class FacturifyPayloadBuilder:
    def __init__(self, account_uuid: str) -> None:
        self._account_uuid = account_uuid

    def build(self, invoice: Invoice, issuer: Party) -> dict:
        if invoice.shipment is None:
            msg = "La factura requiere informacion de Carta Porte"
            raise ValueError(msg)

        tax_amount = invoice.total.amount - invoice.subtotal.amount
        
        factura_block = {
            "version": "4.0",
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tipo": invoice.type.value,
            "forma_de_pago": invoice.payment_form,
            "moneda": invoice.currency,
            "tipo_de_cambio": "1",
            "exportacion": "01",
            "subtotal": invoice.subtotal.amount,
            "impuesto_federal": round(tax_amount, 2),
            "total": invoice.total.amount,
            "conceptos": [self._concepto(c) for c in invoice.items],
            "Complemento": {
                "CartaPorte": self._carta_porte(invoice, issuer)
            },
        }

        payload = {
            "emisor": {"uuid": issuer.external_uuid or self._account_uuid},
            "receptor": {"uuid": invoice.recipient.external_uuid} if invoice.recipient.external_uuid else self._receptor(invoice),
            "factura": factura_block,
        }
        return payload

    def _receptor(self, invoice: Invoice) -> dict:
        party = invoice.recipient
        return {
            "razon_social": party.legal_name,
            "rfc": party.rfc,
            "email": party.email or "",
            "uso_cfdi": invoice.cfdi_use,
            "metodo_de_pago": invoice.payment_method,
            "forma_de_pago": invoice.payment_form,
            "domicilio_fiscal": party.address.zip_code,
        }

    def _concepto(self, item: InvoiceItem) -> dict:
        concept = {
            "cantidad": item.quantity,
            "clave_producto_servicio": item.product_key,
            "clave_unidad_de_medida": item.unit_key,
            "descripcion": item.description,
            "valor_unitario": item.unit_price,
            "total": round(item.quantity * item.unit_price, 2),
            "objeto_imp": "02",
        }
        if item.taxes and item.taxes.get("iva"):
            concept["impuestos"] = {
                "traslados": {
                    "traslado": [
                        {
                            "base": round(item.quantity * item.unit_price, 2),
                            "impuesto": "002",
                            "tipoFactor": "Tasa",
                            "tasaOCuota": item.taxes["iva"] / 100,
                            "importe": round((item.quantity * item.unit_price) * (item.taxes["iva"] / 100), 2),
                        }
                    ]
                }
            }
        return concept

    def _carta_porte(self, invoice: Invoice, issuer: Party) -> dict:
        shipment = invoice.shipment
        assert shipment is not None

        ubicaciones = [
            self._ubicacion(idx, location, invoice, issuer)
            for idx, location in enumerate(shipment.locations, start=1)
        ]
        mercancias = {
            "NumTotalMercancias": len(shipment.goods),
            "PesoNetoTotal": sum(item.weight_kg for item in shipment.goods),
            "PesoBrutoTotal": shipment.total_weight_kg,
            "UnidadPeso": "KGM",
            "Mercancia": [
                {
                    "BienesTransp": good.product_key,
                    "Cantidad": good.quantity,
                    "ClaveUnidad": good.unit_key,
                    "Descripcion": good.description,
                    "PesoEnKg": good.weight_kg,
                }
                | ({"MaterialPeligroso": "Si", "CveMaterialPeligroso": good.dangerous_key}
                   if good.dangerous_material and good.dangerous_key else {})
                for good in shipment.goods
            ],
            "Autotransporte": self._autotransporte(shipment),
        }

        carta_porte = {
            "Version": "3.1",
            "IdCCP": str(uuid.uuid4()).upper(),
            "TranspInternac": self._transporte_internacional(list(shipment.locations)),
            "TotalDistRec": int(shipment.total_distance_km or 0),
            "Ubicaciones": {"Ubicacion": ubicaciones},
            "Mercancias": mercancias,
            "FiguraTransporte": {
                "TiposFigura": [
                    {
                        "TipoFigura": figure.type,
                        "RFCFigura": figure.rfc,
                        "NumLicencia": figure.license or "",
                        "NombreFigura": figure.name,
                    }
                    for figure in shipment.figures
                ]
            }
            if shipment.figures
            else None,
        }

        return {k: v for k, v in carta_porte.items() if v is not None}

    def _autotransporte(self, shipment) -> dict:
        auto = {
            "PermSCT": shipment.permit_type,
            "NumPermisoSCT": shipment.permit_number,
            "IdentificacionVehicular": {
                "ConfigVehicular": shipment.vehicle.configuration,
                "PlacaVM": shipment.vehicle.plate,
                "AnioModeloVM": str(getattr(shipment.vehicle, "model_year", "2025")),
                "PesoBrutoVehicular": str(getattr(shipment.vehicle, "gross_weight", "46.5")),
            },
            "Seguros": {
                "AseguraRespCivil": shipment.vehicle.insurance_company or "",
                "PolizaRespCivil": shipment.vehicle.insurance_policy or "",
                "PrimaSeguro": str(getattr(shipment.vehicle, "insurance_premium", "1200")),
            },
        }
        
        if hasattr(shipment.vehicle, "trailers") and shipment.vehicle.trailers:
            auto["Remolques"] = {
                "Remolque": [
                    {
                        "SubTipoRem": trailer.get("subtype", "CTR007"),
                        "Placa": trailer.get("plate", ""),
                    }
                    for trailer in shipment.vehicle.trailers
                ]
            }
        
        return auto

    def _ubicacion(
        self,
        index: int,
        location: ShipmentLocation,
        invoice: Invoice,
        issuer: Party,
    ) -> dict:
        is_origin = location.type == ShipmentLocationType.origin
        rfc = issuer.rfc if is_origin else invoice.recipient.rfc
        
        domicilio = {
            "Calle": location.street,
            "CodigoPostal": location.zip_code,
        }
        
        if location.city:
            domicilio["Municipio"] = location.city
        if hasattr(location, "locality") and location.locality:
            domicilio["Localidad"] = location.locality
        
        domicilio["Estado"] = location.state
        domicilio["Pais"] = location.country
        
        data = {
            "TipoUbicacion": location.type.value.capitalize(),
            "IDUbicacion": f"{'OR' if is_origin else 'DE'}{index-1:06d}",
            "RFCRemitenteDestinatario": rfc,
            "FechaHoraSalidaLlegada": location.datetime.isoformat(),
            "Domicilio": domicilio,
        }
        
        if not is_origin:
            data["DistanciaRecorrida"] = int(invoice.shipment.total_distance_km or 0)
        
        return data

    def _transporte_internacional(self, locations: list[ShipmentLocation]) -> str:
        if any(location.country != "MEX" for location in locations):
            return "Si"
        return "No"
