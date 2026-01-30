from __future__ import annotations

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.dtos import CartaPorteRequest, CartaPorteResponse, FacturifyCartaPorteRequest
from app.application.services.create_carta_porte import CreateCartaPorteService, UnitOfWorkFactory
from app.application.transformers import FacturifyToInternalTransformer
from app.core import exceptions
from app.core.error_parser import FacturifyErrorParser
from app.interfaces.api.deps import get_create_carta_porte_service, get_uow_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/cfdi", tags=["cfdi"])


@router.post("/carta-porte", response_model=CartaPorteResponse, status_code=status.HTTP_201_CREATED)
async def create_carta_porte_endpoint(
    payload: CartaPorteRequest,
    service: CreateCartaPorteService = Depends(get_create_carta_porte_service),
) -> CartaPorteResponse:
    logger.info("=" * 80)
    logger.info("REQUEST RECIBIDO EN /v1/cfdi/carta-porte")
    logger.info("JSON recibido:")
    logger.info(json.dumps(payload.model_dump(mode="json"), indent=2, ensure_ascii=False))
    logger.info("=" * 80)
    
    try:
        invoice = await service.execute(payload)
    except exceptions.ExternalServiceError as error:
        logger.error("Error de Facturify/SAT: %s", str(error))
        error_detail = {
            "message": str(error),
            "type": "external_service_error",
            "hint": "Verifica los datos fiscales del receptor y emisor"
        }
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_detail) from error
    except exceptions.BillingError as error:
        logger.error("Error al procesar carta porte: %s", str(error))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    logger.info("=" * 80)
    logger.info("RESPUESTA DE FACTURIFY:")
    logger.info(json.dumps(invoice.facturify_response, indent=2, ensure_ascii=False))
    logger.info("=" * 80)

    return CartaPorteResponse(
        invoice_id=invoice.id,
        status=invoice.status.value,
        facturify_uuid=invoice.facturify_uuid,
        facturify_status=invoice.status.value,
        facturify_response=invoice.facturify_response,
    )


@router.post("/carta-porte/facturify", response_model=CartaPorteResponse, status_code=status.HTTP_201_CREATED)
async def create_carta_porte_facturify_format(
    payload: FacturifyCartaPorteRequest,
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> CartaPorteResponse:
    from app.domain.enums import InvoiceStatus, InvoiceType, ComplementType, TransportMode, ShipmentLocationType
    from app.domain.entities import Invoice, InvoiceItem, Shipment, ShipmentLocation, GoodsItem, TransportFigure, Vehicle, Party, Address, Money
    from uuid import uuid4
    from app.interfaces.api.deps import get_app_settings
    from app.infrastructure.http.facturify_client import FacturifyClient
    from datetime import datetime
    
    logger.info("JSON recibido en /v1/cfdi/carta-porte/facturify:")
    logger.info(json.dumps(payload.model_dump(mode="json", exclude_none=True), indent=2, ensure_ascii=False))
    
    facturify_payload = payload.model_dump(mode="json", exclude_none=True)
    
    # Obtener o crear el receptor (cliente) basado en el UUID de Facturify
    async with uow_factory() as uow:
        receptor_rfc = payload.receptor.rfc or "XAXX010101000"
        recipient = await uow.clients.get_by_rfc(receptor_rfc)
        
        if recipient is None:
            # El régimen fiscal debe ser código de 3 dígitos, no texto completo
            tax_regime = "616"  # Default: Sin obligaciones fiscales
            if payload.receptor.regimen:
                # Si viene un código de 3 dígitos, usarlo; si no, usar default
                if len(payload.receptor.regimen) <= 3 and payload.receptor.regimen.isdigit():
                    tax_regime = payload.receptor.regimen
            
            recipient = Party(
                legal_name=payload.receptor.razon_social or "Cliente Genérico",
                rfc=receptor_rfc,
                tax_regime=tax_regime,
                email=None,
                address=Address(
                    street="Sin calle",
                    exterior_number="SN",
                    neighborhood="Sin colonia",
                    city="Sin ciudad",
                    state="Sin estado",
                    country="MEX",
                    zip_code=payload.receptor.cp or "00000",
                ),
            )
            recipient = await uow.clients.upsert(recipient)
    
    # Enviar directamente a Facturify sin transformaciones
    try:
        settings = get_app_settings()
        facturify_client = FacturifyClient(
            base_url=settings.facturify_base_url,
            timeout=settings.facturify_timeout,
            max_retries=settings.facturify_max_retries,
            retry_backoff=settings.facturify_retry_backoff,
        )
        
        facturify_response = await facturify_client.create_carta_porte(facturify_payload)
    except exceptions.ExternalServiceError as error:
        error_detail = {
            "message": str(error),
            "type": "external_service_error",
            "hint": "Verifica los datos fiscales del receptor y emisor en el SAT"
        }
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_detail) from error
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    # Extraer datos de la respuesta de Facturify
    data = facturify_response.get("data", {})
    cfdi_uuid = data.get("cfdi_uuid") or facturify_response.get("cfdi_uuid")
    serie = data.get("serie")
    folio = data.get("folio")
    factura_id = data.get("factura_id")
    provider = data.get("provider")
    
    # Construir entidades del dominio a partir del payload de Facturify
    factura = payload.factura
    carta_porte = factura.Complemento.CartaPorte
    
    # Items de la factura
    items = [
        InvoiceItem(
            product_key=concepto.clave_producto_servicio,
            description=concepto.descripcion,
            quantity=concepto.cantidad,
            unit_key=concepto.clave_unidad_de_medida,
            unit_price=concepto.valor_unitario,
            taxes=None,
        )
        for concepto in factura.conceptos
    ]
    
    # Ubicaciones del envío
    locations = [
        ShipmentLocation(
            type=ShipmentLocationType.origin if ubicacion.TipoUbicacion == "Origen" else ShipmentLocationType.destination,
            datetime=datetime.fromisoformat(ubicacion.FechaHoraSalidaLlegada.replace("T", " ")),
            street=ubicacion.Domicilio.Calle,
            exterior_number=ubicacion.Domicilio.NumeroExterior or "SN",
            neighborhood=ubicacion.Domicilio.Colonia or "Sin colonia",
            city=ubicacion.Domicilio.Municipio or "Sin municipio",
            state=ubicacion.Domicilio.Estado,
            country=ubicacion.Domicilio.Pais,
            zip_code=ubicacion.Domicilio.CodigoPostal,
            latitude=None,
            longitude=None,
            reference=None,
        )
        for ubicacion in carta_porte.Ubicaciones.Ubicacion
    ]
    
    # Mercancías
    goods = [
        GoodsItem(
            description=mercancia.Descripcion,
            product_key=mercancia.BienesTransp,
            quantity=mercancia.Cantidad,
            unit_key=mercancia.ClaveUnidad,
            weight_kg=mercancia.PesoEnKg,
            value=0.0,
            dangerous_material=mercancia.MaterialPeligroso == "Si" if mercancia.MaterialPeligroso else False,
            dangerous_key=mercancia.CveMaterialPeligroso,
        )
        for mercancia in carta_porte.Mercancias.Mercancia
    ]
    
    # Figuras de transporte
    figures = [
        TransportFigure(
            type=figura.TipoFigura,
            rfc=figura.RFCFigura,
            name=figura.NombreFigura,
            license=figura.NumLicencia,
            role_description=None,
        )
        for figura in carta_porte.FiguraTransporte.TiposFigura
    ]
    
    # Vehículo
    autotransporte = carta_porte.Mercancias.Autotransporte
    vehicle = Vehicle(
        configuration=autotransporte.IdentificacionVehicular.ConfigVehicular,
        plate=autotransporte.IdentificacionVehicular.PlacaVM,
        federal_permit=autotransporte.NumPermisoSCT,
        insurance_company=autotransporte.Seguros.AseguraRespCivil,
        insurance_policy=autotransporte.Seguros.PolizaRespCivil,
    )
    
    # Envío completo
    shipment = Shipment(
        transport_mode=TransportMode.autotransporte_federal,
        permit_type=autotransporte.PermSCT,
        permit_number=autotransporte.NumPermisoSCT,
        total_distance_km=carta_porte.TotalDistRec,
        total_weight_kg=carta_porte.Mercancias.PesoBrutoTotal,
        vehicle=vehicle,
        locations=locations,
        goods=goods,
        figures=figures,
    )
    
    # Crear la factura
    invoice = Invoice(
        issuer_id=None,
        recipient=recipient,
        type=InvoiceType.ingreso if factura.tipo == "ingreso" else InvoiceType.traslado,
        complement=ComplementType.carta_porte,
        currency=factura.moneda,
        subtotal=Money(amount=factura.subtotal, currency=factura.moneda),
        total=Money(amount=factura.total, currency=factura.moneda),
        cfdi_use=factura.uso_cfdi or "S01",
        payment_form=factura.forma_de_pago,
        payment_method=factura.metodo_de_pago,
        expedition_place=factura.lugar_expedicion or "00000",
        items=items,
        shipment=shipment,
    )
    
    # Guardar la factura en la base de datos
    async with uow_factory() as uow:
        invoice = await uow.invoices.create(invoice)
        
        if cfdi_uuid:
            invoice.mark_issued(
                uuid=cfdi_uuid,
                payload=None,
                serie=serie,
                folio=folio,
                factura_id=factura_id,
                provider=provider,
            )
        else:
            invoice.mark_failed()
        
        await uow.invoices.update(invoice)
    
    status_value = InvoiceStatus.issued.value if cfdi_uuid else InvoiceStatus.failed.value
    
    return CartaPorteResponse(
        invoice_id=invoice.id,
        status=status_value,
        facturify_uuid=cfdi_uuid,
        facturify_status=status_value,
        facturify_response=facturify_response,
    )


@router.get("/{invoice_id}", response_model=CartaPorteResponse)
async def get_invoice_endpoint(
    invoice_id: UUID,
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> CartaPorteResponse:
    async with uow_factory() as uow:
        invoice = await uow.invoices.get_by_id(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factura no encontrada")

    return CartaPorteResponse(
        invoice_id=invoice.id,
        status=invoice.status.value,
        facturify_uuid=invoice.facturify_uuid,
        facturify_status=invoice.status.value,
        facturify_response=invoice.facturify_response,
    )
