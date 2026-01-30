"""Transformer para convertir formato Facturify a formato interno."""
from __future__ import annotations

from datetime import datetime

from app.application.dtos import (
    AddressDTO,
    CartaPorteRequest,
    InvoiceItemDTO,
    PartyDTO,
    ShipmentDTO,
    ShipmentGoodsDTO,
    ShipmentLocationDTO,
    ShipmentVehicleDTO,
    TransportFigureDTO,
)
from app.application.dtos.facturify_format import FacturifyCartaPorteRequest
from app.domain.enums import ShipmentLocationType


class FacturifyToInternalTransformer:
    """Transforma el formato de entrada Facturify al formato interno CartaPorteRequest."""

    @staticmethod
    def transform(facturify_request: FacturifyCartaPorteRequest) -> CartaPorteRequest:
        """Convierte FacturifyCartaPorteRequest a CartaPorteRequest."""
        factura = facturify_request.factura
        carta_porte = factura.Complemento.CartaPorte

        items = [
            InvoiceItemDTO(
                product_key=concepto.clave_producto_servicio,
                description=concepto.descripcion,
                quantity=concepto.cantidad,
                unit_key=concepto.clave_unidad_de_medida,
                unit_price=concepto.valor_unitario,
                tax_percentage=FacturifyToInternalTransformer._extract_tax_percentage(concepto),
            )
            for concepto in factura.conceptos
        ]

        locations = [
            ShipmentLocationDTO(
                type=ShipmentLocationType.origin
                if ubicacion.TipoUbicacion == "Origen"
                else ShipmentLocationType.destination,
                datetime=datetime.fromisoformat(ubicacion.FechaHoraSalidaLlegada),
                street=ubicacion.Domicilio.Calle,
                exterior_number=ubicacion.Domicilio.NumeroExterior or "S/N",
                neighborhood=ubicacion.Domicilio.Colonia or "",
                city=ubicacion.Domicilio.Municipio or "",
                state=ubicacion.Domicilio.Estado,
                country=ubicacion.Domicilio.Pais,
                zip_code=ubicacion.Domicilio.CodigoPostal,
                locality=ubicacion.Domicilio.Localidad,
            )
            for ubicacion in carta_porte.Ubicaciones.Ubicacion
        ]

        goods = [
            ShipmentGoodsDTO(
                description=mercancia.Descripcion,
                product_key=mercancia.BienesTransp,
                quantity=mercancia.Cantidad,
                unit_key=mercancia.ClaveUnidad,
                weight_kg=mercancia.PesoEnKg,
                value=factura.subtotal / len(carta_porte.Mercancias.Mercancia),
                dangerous_material=bool(mercancia.MaterialPeligroso),
                dangerous_key=mercancia.CveMaterialPeligroso,
            )
            for mercancia in carta_porte.Mercancias.Mercancia
        ]

        figures = [
            TransportFigureDTO(
                type=figura.TipoFigura,
                rfc=figura.RFCFigura,
                name=figura.NombreFigura,
                license=figura.NumLicencia,
            )
            for figura in carta_porte.FiguraTransporte.TiposFigura
        ]

        auto = carta_porte.Mercancias.Autotransporte
        trailers = None
        if auto.Remolques and auto.Remolques.Remolque:
            trailers = [
                {"subtype": remolque.SubTipoRem, "plate": remolque.Placa}
                for remolque in auto.Remolques.Remolque
            ]

        vehicle = ShipmentVehicleDTO(
            configuration=auto.IdentificacionVehicular.ConfigVehicular,
            plate=auto.IdentificacionVehicular.PlacaVM,
            federal_permit=auto.PermSCT,
            insurance_company=auto.Seguros.AseguraRespCivil,
            insurance_policy=auto.Seguros.PolizaRespCivil,
            model_year=auto.IdentificacionVehicular.AnioModeloVM,
            gross_weight=auto.IdentificacionVehicular.PesoBrutoVehicular,
            insurance_premium=auto.Seguros.PrimaSeguro,
            trailers=trailers,
        )

        shipment = ShipmentDTO(
            transport_mode="01",
            permit_type=auto.PermSCT,
            permit_number=auto.NumPermisoSCT,
            total_distance_km=carta_porte.TotalDistRec,
            total_weight_kg=carta_porte.Mercancias.PesoBrutoTotal,
            vehicle=vehicle,
            locations=locations,
            goods=goods,
            figures=figures,
        )

        first_location = carta_porte.Ubicaciones.Ubicacion[0]
        recipient = PartyDTO(
            legal_name=facturify_request.receptor.razon_social or "PUBLICO EN GENERAL",
            rfc=facturify_request.receptor.rfc or first_location.RFCRemitenteDestinatario,
            tax_regime=facturify_request.receptor.regimen or "616",
            email=None,
            address=AddressDTO(
                street=first_location.Domicilio.Calle,
                exterior_number=first_location.Domicilio.NumeroExterior or "S/N",
                neighborhood=first_location.Domicilio.Colonia or "",
                city=first_location.Domicilio.Municipio or "",
                state=first_location.Domicilio.Estado,
                country=first_location.Domicilio.Pais,
                zip_code=facturify_request.receptor.cp or first_location.Domicilio.CodigoPostal,
            ),
        )

        return CartaPorteRequest(
            facturify_issuer_uuid=str(facturify_request.emisor.uuid),
            cfdi_type=factura.tipo,
            recipient=recipient,
            cfdi_use=factura.uso_cfdi or "G01",
            payment_form=facturify_request.receptor.forma_de_pago or factura.forma_de_pago,
            payment_method=facturify_request.receptor.metodo_de_pago or factura.metodo_de_pago,
            expedition_place=facturify_request.emisor.cp or first_location.Domicilio.CodigoPostal,
            currency=factura.moneda,
            subtotal=factura.subtotal,
            total=factura.total,
            items=items,
            shipment=shipment,
        )

    @staticmethod
    def _extract_tax_percentage(concepto) -> float | None:
        """Extrae el porcentaje de IVA del concepto."""
        if not concepto.impuestos or not concepto.impuestos.traslados:
            return None

        for traslado in concepto.impuestos.traslados.traslado:
            if traslado.impuesto == "002":
                return traslado.tasaOCuota * 100

        return None
