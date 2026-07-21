"""Endpoints CFDI Carta Porte — usa FacturaloPlus como PAC."""
from __future__ import annotations

import base64
import io
import json
import logging
import zipfile
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response

from app.application.dtos import (
    CartaPorteResponse,
    FormTemplateResponse,
    InvoiceHistoryItem,
    InvoiceHistoryResponse,
)
from app.application.dtos.facturify_format import FacturifyCartaPorteRequest
from app.application.services.carta_porte_validation import CartaPorteValidationError
from app.core import exceptions
from app.core.config import Settings
from app.domain.entities import (
    Address,
    GoodsItem,
    Invoice,
    InvoiceItem,
    Money,
    Party,
    Shipment,
    ShipmentLocation,
    TransportFigure,
    Vehicle,
)
from app.domain.enums import (
    CancelMotivo,
    ComplementType,
    InvoiceStatus,
    InvoiceType,
    ShipmentLocationType,
    TransportMode,
)
from app.infrastructure.http.facturalo_client import FacturaloPlusClient
from app.infrastructure.http.logistics_client import LogisticsClient
from app.infrastructure.mappers.facturalo_payload import FacturaloPayloadBuilder
from app.interfaces.api.cfdi_error_response import (
    external_service_error_to_detail,
    validation_issues_to_detail,
)
from app.interfaces.api.deps import (
    UnitOfWorkFactory,
    get_app_settings,
    get_facturalo_client,
    get_facturalo_payload_builder,
    get_logistics_client,
    get_uow_factory,
)
from app.interfaces.api.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/cfdi", tags=["cfdi"])


def _extract_data_block(response: dict | None) -> dict:
    """Extrae el bloque `data` del payload de FacturaloPlus."""
    if not response:
        return {}
    data = response.get("data", {})
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            return {}
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Background task — llama a FacturaloPlus y persiste el resultado
# ---------------------------------------------------------------------------

async def _timbrado_background(
    invoice_id: UUID,
    sat_payload: dict,
    trip_id: int | None,
    uow_factory: UnitOfWorkFactory,
    facturalo_client: FacturaloPlusClient,
    logistics_client: LogisticsClient,
) -> None:
    """Ejecuta el timbrado con FacturaloPlus y actualiza la factura en la BD.

    Se corre como BackgroundTask para que el endpoint responda de forma
    inmediata con status='pending' sin bloquear al usuario.
    """
    logger.info("Background timbrado iniciado para invoice_id=%s", invoice_id)

    # --- 1. Verificar que la factura exista (transacción breve) ---
    async with uow_factory() as uow:
        invoice = await uow.invoices.get_by_id(invoice_id)

    if invoice is None:
        logger.error("Background timbrado: factura %s no encontrada en la BD", invoice_id)
        return

    # --- 2. Llamar a FacturaloPlus (fuera de la transacción para no mantener el pool ocupado) ---
    try:
        facturalo_response = await facturalo_client.create_carta_porte(sat_payload)
    except exceptions.ExternalServiceError as error:
        logger.error("Background timbrado error FacturaloPlus invoice=%s: %s", invoice_id, str(error))
        folio_to_release = invoice.folio
        invoice.mark_failed()
        invoice.pac_response = {"error": str(error), "code": getattr(error, "code", "external_error")}
        async with uow_factory() as uow:
            await uow.invoices.update(invoice)
            if folio_to_release is not None:
                released = await uow.invoices.release_folio_if_latest(folio_to_release)
                logger.info(
                    "Timbrado fallido invoice=%s: folio %s %s",
                    invoice_id,
                    folio_to_release,
                    "liberado" if released else "no liberado (ya hubo otro allocate)",
                )
        return

    # --- 3. Procesar respuesta y persistir resultado (transacción breve) ---
    data = _extract_data_block(facturalo_response)
    cfdi_uuid: str | None = data.get("UUID")

    if cfdi_uuid:
        data.setdefault("cfdi_uuid", cfdi_uuid)
        if invoice.serie:
            data.setdefault("serie", invoice.serie)
        if invoice.folio is not None:
            data.setdefault("folio", invoice.folio)
        facturalo_response["data"] = data

        pdf_b64: str | None = data.get("PDF")
        xml_text: str | None = data.get("XML")

        invoice.mark_issued(
            uuid=cfdi_uuid,
            payload=facturalo_response,
            serie=invoice.serie,
            folio=invoice.folio,
            provider="facturalo",
            xml=xml_text,
            pdf_b64=pdf_b64,
        )
        invoice.form_snapshot = sat_payload
        async with uow_factory() as uow:
            await uow.invoices.update(invoice)
    else:
        logger.warning("Background timbrado: FacturaloPlus no devolvió UUID para invoice=%s", invoice_id)
        folio_to_release = invoice.folio
        invoice.mark_failed()
        invoice.pac_response = facturalo_response
        async with uow_factory() as uow:
            await uow.invoices.update(invoice)
            if folio_to_release is not None:
                released = await uow.invoices.release_folio_if_latest(folio_to_release)
                logger.info(
                    "Timbrado sin UUID invoice=%s: folio %s %s",
                    invoice_id,
                    folio_to_release,
                    "liberado" if released else "no liberado (ya hubo otro allocate)",
                )

    logger.info("Background timbrado completado invoice=%s status=%s uuid=%s", invoice_id, invoice.status, cfdi_uuid)

    # Notificar a logistics (fire-and-forget, fuera de la transacción)
    if cfdi_uuid and trip_id:
        ccp = f"{invoice.serie} {invoice.folio}" if invoice.serie and invoice.folio else None
        try:
            await logistics_client.notify_cfdi_issued(trip_id=trip_id, cfdi_uuid=cfdi_uuid, ccp=ccp)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Background timbrado: fallo al notificar logistics trip=%s: %s", trip_id, exc)


# ---------------------------------------------------------------------------
# POST /v1/cfdi/carta-porte/facturify
# ---------------------------------------------------------------------------

@router.post("/carta-porte/facturify", response_model=CartaPorteResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("20/minute")
async def create_carta_porte_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: FacturifyCartaPorteRequest = Body(...),
    settings: Settings = Depends(get_app_settings),
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    facturalo_client: FacturaloPlusClient = Depends(get_facturalo_client),
    payload_builder: FacturaloPayloadBuilder = Depends(get_facturalo_payload_builder),
    logistics_client: LogisticsClient = Depends(get_logistics_client),
) -> CartaPorteResponse:
    """Acepta la solicitud de timbrado y responde de inmediato con status='pending'.

    El timbrado real se ejecuta en un background task para evitar timeouts
    en payloads grandes (600+ mercancías) donde FacturaloPlus puede tardar
    más de 3 minutos generando el PDF.

    El cliente debe hacer polling a GET /v1/cfdi/{invoice_id} hasta que
    status sea 'issued' o 'failed'.
    """
    from app.application.services.carta_porte_validation import assert_valid_carta_porte_request

    try:
        assert_valid_carta_porte_request(
            payload,
            emisor_rfc_config=settings.facturalo_emisor_rfc,
            emisor_cp_config=settings.facturalo_emisor_cp,
        )
    except CartaPorteValidationError as error:
        logger.warning("Validación carta porte fallida: %d errores", len(error.issues))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation_issues_to_detail(error.issues),
        ) from error

    factura = payload.factura
    carta_porte = factura.Complemento.CartaPorte

    # 1. Construir el payload SAT antes de abrir la transacción (operación pura, sin IO)
    sat_payload = payload_builder.build(payload)

    # 2. Upsert receptor, persistir factura en status=pending
    async with uow_factory() as uow:
        receptor_rfc = (payload.receptor.rfc or "XAXX010101000").strip()
        recipient = await uow.clients.get_by_rfc(receptor_rfc)

        if recipient is None:
            tax_regime = "616"
            if payload.receptor.regimen:
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

        items = [
            InvoiceItem(
                product_key=c.clave_producto_servicio,
                description=c.descripcion,
                quantity=c.cantidad,
                unit_key=c.clave_unidad_de_medida,
                unit_price=c.valor_unitario,
                taxes=None,
            )
            for c in factura.conceptos
        ]

        locations = [
            ShipmentLocation(
                type=(
                    ShipmentLocationType.origin
                    if u.TipoUbicacion == "Origen"
                    else ShipmentLocationType.destination
                ),
                datetime=datetime.fromisoformat(u.FechaHoraSalidaLlegada.replace(" ", "T")),
                street=u.Domicilio.Calle,
                exterior_number=u.Domicilio.NumeroExterior or "SN",
                neighborhood=u.Domicilio.Colonia or "Sin colonia",
                city=u.Domicilio.Municipio or "Sin municipio",
                state=u.Domicilio.Estado,
                country=u.Domicilio.Pais,
                zip_code=u.Domicilio.CodigoPostal,
                latitude=None,
                longitude=None,
                reference=u.Domicilio.Referencia,
            )
            for u in carta_porte.Ubicaciones.Ubicacion
        ]

        goods = [
            GoodsItem(
                description=m.Descripcion,
                product_key=m.BienesTransp,
                quantity=m.Cantidad,
                unit_key=m.ClaveUnidad,
                weight_kg=m.PesoEnKg,
                value=0.0,
                dangerous_material=bool(
                    m.MaterialPeligroso and m.MaterialPeligroso.strip().lower() in ("sí", "si", "s")
                ),
                dangerous_key=m.CveMaterialPeligroso,
            )
            for m in carta_porte.Mercancias.Mercancia
        ]

        figures = [
            TransportFigure(
                type=f.TipoFigura,
                rfc=f.RFCFigura,
                name=f.NombreFigura,
                license=f.NumLicencia,
                role_description=None,
            )
            for f in carta_porte.FiguraTransporte.TiposFigura
        ]

        auto = carta_porte.Mercancias.Autotransporte
        vehicle = Vehicle(
            configuration=auto.IdentificacionVehicular.ConfigVehicular,
            plate=auto.IdentificacionVehicular.PlacaVM,
            federal_permit=auto.NumPermisoSCT,
            insurance_company=auto.Seguros.AseguraRespCivil,
            insurance_policy=auto.Seguros.PolizaRespCivil,
        )

        shipment = Shipment(
            transport_mode=TransportMode.autotransporte_federal,
            permit_type=auto.PermSCT,
            permit_number=auto.NumPermisoSCT,
            total_distance_km=carta_porte.TotalDistRec,
            total_weight_kg=carta_porte.Mercancias.PesoBrutoTotal,
            vehicle=vehicle,
            locations=locations,
            goods=goods,
            figures=figures,
        )

        invoice = Invoice(
            recipient=recipient,
            type=InvoiceType.ingreso if factura.tipo == "ingreso" else InvoiceType.traslado,
            complement=ComplementType.carta_porte,
            currency=factura.moneda,
            subtotal=Money(amount=factura.subtotal, currency=factura.moneda),
            total=Money(amount=factura.total, currency=factura.moneda),
            cfdi_use=factura.uso_cfdi or "S01",
            payment_form=factura.forma_de_pago,
            payment_method=factura.metodo_de_pago,
            expedition_place=(
                factura.lugar_expedicion or payload_builder.resolve_emisor(payload)[3] or "00000"
            ),
            items=items,
            shipment=shipment,
            trip_id=payload.trip_id,
            status=InvoiceStatus.pending,
            request_snapshot=payload.ui_draft,
        )

        invoice = await uow.invoices.create(invoice)

    # El folio/serie es autoritativo del backend (secuencia invoices_folio_seq),
    # no del formulario: se inyecta aquí porque solo se conoce tras crear la factura.
    sat_payload["Comprobante"]["Serie"] = invoice.serie
    if invoice.folio is not None:
        sat_payload["Comprobante"]["Folio"] = str(invoice.folio)

    # 3. Despachar timbrado como background task (respuesta inmediata al cliente)
    background_tasks.add_task(
        _timbrado_background,
        invoice_id=invoice.id,
        sat_payload=sat_payload,
        trip_id=payload.trip_id,
        uow_factory=uow_factory,
        facturalo_client=facturalo_client,
        logistics_client=logistics_client,
    )

    logger.info(
        "Carta Porte aceptada, timbrado en background. invoice_id=%s trip_id=%s mercancias=%d",
        invoice.id,
        payload.trip_id,
        len(carta_porte.Mercancias.Mercancia),
    )

    return CartaPorteResponse(
        invoice_id=invoice.id,
        status=InvoiceStatus.pending.value,
        cfdi_uuid=None,
        pac_response=None,
        trip_id=payload.trip_id,
    )


# ---------------------------------------------------------------------------
# GET /v1/cfdi/{invoice_id}
# ---------------------------------------------------------------------------

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
        cfdi_uuid=invoice.cfdi_uuid,
        pac_response=invoice.pac_response,
        trip_id=invoice.trip_id,
    )


# ---------------------------------------------------------------------------
# GET /v1/cfdi/{invoice_id}/form-template
# ---------------------------------------------------------------------------

@router.get("/{invoice_id}/form-template", response_model=FormTemplateResponse)
@limiter.limit("60/minute")
async def get_form_template_endpoint(
    request: Request,
    invoice_id: UUID,
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> FormTemplateResponse:
    async with uow_factory() as uow:
        invoice = await uow.invoices.get_by_id(invoice_id)
    snapshot = None
    if invoice is not None:
        # Preferir snapshot UI (prellenado del dialog); fallback al SAT histórico.
        snapshot = invoice.request_snapshot or invoice.form_snapshot
    if (
        invoice is None
        or invoice.status != InvoiceStatus.issued
        or not snapshot
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plantilla no disponible (solo facturas timbradas con snapshot).",
        )
    return FormTemplateResponse(invoice_id=invoice.id, payload=snapshot)


# ---------------------------------------------------------------------------
# GET /v1/cfdi/by-receptor/{rfc}/last-form
# ---------------------------------------------------------------------------


@router.get("/by-receptor/{rfc}/last-form", response_model=FormTemplateResponse)
async def get_last_form_by_receptor_endpoint(
    rfc: str,
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> FormTemplateResponse:
    """Última factura issued del receptor con ui_draft (request_snapshot) para precargar el dialog."""
    rfc_norm = (rfc or "").strip().upper()
    if not rfc_norm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RFC es requerido",
        )

    async with uow_factory() as uow:
        invoice = await uow.invoices.get_last_issued_with_request_snapshot_by_rfc(rfc_norm)

    if invoice is None or not invoice.request_snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay formulario previo para este receptor.",
        )

    return FormTemplateResponse(invoice_id=invoice.id, payload=invoice.request_snapshot)


# ---------------------------------------------------------------------------
# GET /v1/cfdi/by-trip/{trip_id}
# ---------------------------------------------------------------------------


@router.get("/by-trip/{trip_id}", response_model=InvoiceHistoryResponse)
async def get_invoice_history_by_trip_endpoint(
    trip_id: int,
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> InvoiceHistoryResponse:
    """Historial de facturas (vigentes, canceladas o fallidas) de un viaje.

    Permite mostrar en el frontend que un viaje tuvo una factura cancelada
    (con acceso a su PDF/XML para auditoría) aunque el viaje ya no tenga un
    timbre_uuid activo.
    """
    async with uow_factory() as uow:
        invoices = await uow.invoices.list_by_trip_id(trip_id)

    items = [
        InvoiceHistoryItem(
            invoice_id=invoice.id,
            status=invoice.status.value,
            serie=invoice.serie,
            folio=invoice.folio,
            cfdi_uuid=invoice.cfdi_uuid,
            cancel_motivo=invoice.cancel_motivo,
            cancelled_at=invoice.cancelled_at,
            created_at=invoice.created_at,
            pdf_url=f"/v1/cfdi/{invoice.cfdi_uuid}/pdf" if invoice.cfdi_uuid else None,
            xml_url=f"/v1/cfdi/{invoice.cfdi_uuid}/xml" if invoice.cfdi_uuid else None,
        )
        for invoice in invoices
    ]
    return InvoiceHistoryResponse(trip_id=trip_id, invoices=items)


# ---------------------------------------------------------------------------
# PUT /v1/cfdi/{cfdi_uuid}/cancel
# ---------------------------------------------------------------------------

@router.put("/{cfdi_uuid}/cancel")
async def cancel_invoice_endpoint(
    cfdi_uuid: str,
    motivo: str = Query(default="02", description="Motivo de cancelación SAT (01-04)"),
    folio_sustitucion: str = Query(
        default="",
        description="UUID del CFDI que sustituye al cancelado (obligatorio si motivo=01)",
    ),
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    facturalo_client: FacturaloPlusClient = Depends(get_facturalo_client),
    logistics_client: LogisticsClient = Depends(get_logistics_client),
) -> dict:
    """Cancela un CFDI en el SAT usando FacturaloPlus y sincroniza el estatus local."""
    valid_motivos = {m.value for m in CancelMotivo}
    if motivo not in valid_motivos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": (
                    f"Motivo de cancelación inválido: {motivo}. "
                    f"Use uno de {sorted(valid_motivos)}."
                ),
                "type": "validation_error",
            },
        )
    if motivo == CancelMotivo.con_relacion.value and not folio_sustitucion:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": (
                    "folio_sustitucion es obligatorio cuando motivo=01 "
                    "(comprobante con relación)."
                ),
                "type": "validation_error",
            },
        )

    async with uow_factory() as uow:
        invoice = await uow.invoices.get_by_cfdi_uuid(cfdi_uuid)

    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factura no encontrada para el UUID proporcionado",
        )

    if invoice.status == InvoiceStatus.canceled:
        return {"message": "La factura ya se encontraba cancelada.", "status": invoice.status.value}

    if invoice.status != InvoiceStatus.issued:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    "Solo se pueden cancelar facturas timbradas "
                    f"(status actual: {invoice.status.value})."
                ),
                "type": "validation_error",
            },
        )

    rfc_receptor = invoice.recipient.rfc if invoice.recipient else ""
    total = str(invoice.total.amount)
    # El RFC emisor real usado al timbrar (puede diferir del .env si vino de
    # empresa_fiscal en adrh_logistics) se toma del snapshot guardado, no del entorno.
    snapshot_comprobante = (invoice.form_snapshot or {}).get("Comprobante") or {}
    rfc_emisor = snapshot_comprobante.get("Emisor", {}).get("Rfc", "")

    try:
        response = await facturalo_client.cancel_invoice(
            cfdi_uuid=cfdi_uuid,
            rfc_receptor=rfc_receptor,
            total=total,
            motivo=motivo,
            rfc_emisor=rfc_emisor,
            folio_sustitucion=folio_sustitucion,
        )
    except exceptions.ExternalServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=external_service_error_to_detail(error),
        ) from error

    invoice.mark_canceled(
        motivo=motivo, response=response, folio_sustitucion=folio_sustitucion or None
    )

    async with uow_factory() as uow:
        await uow.invoices.update(invoice)

    logger.info(
        "Factura cancelada invoice=%s cfdi_uuid=%s motivo=%s", invoice.id, cfdi_uuid, motivo
    )

    if invoice.trip_id:
        try:
            await logistics_client.notify_cfdi_cancelled(
                trip_id=invoice.trip_id,
                cfdi_uuid=cfdi_uuid,
                motivo=motivo,
                cancelled_at=invoice.cancelled_at,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Cancelación: fallo al notificar logistics trip=%s: %s", invoice.trip_id, exc
            )

    return {
        "message": response.get("message", "La factura se canceló exitosamente."),
        "status": invoice.status.value,
    }


# ---------------------------------------------------------------------------
# GET /v1/cfdi/{cfdi_uuid}/pdf
# ---------------------------------------------------------------------------

@router.get("/{cfdi_uuid}/pdf")
async def get_invoice_pdf_endpoint(
    cfdi_uuid: str,
    download: bool = Query(default=False, description="Si true, fuerza descarga en lugar de vista previa"),
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> Response:
    """Retorna el PDF del CFDI como binario listo para abrir en el navegador."""
    async with uow_factory() as uow:
        doc = await uow.invoices.get_pac_response_by_cfdi_uuid(cfdi_uuid)

    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factura no encontrada")

    # Prioridad: columna dedicada cfdi_pdf_b64 → fallback a pac_response.data.PDF
    pdf_b64 = doc.get("cfdi_pdf_b64") or _extract_data_block(doc.get("pac_response")).get("PDF")

    if pdf_b64:
        disposition = "attachment" if download else "inline"
        return Response(
            content=base64.b64decode(pdf_b64),
            media_type="application/pdf",
            headers={"Content-Disposition": f'{disposition}; filename="factura_{cfdi_uuid}.pdf"'},
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "message": "PDF no disponible para esta factura.",
            "type": "not_found",
            "code": "pdf_not_found",
            "hint": "Verifique que FACTURALO_PDF_PLANTILLA esté configurada.",
        },
    )


# ---------------------------------------------------------------------------
# GET /v1/cfdi/{cfdi_uuid}/xml
# ---------------------------------------------------------------------------

@router.get("/{cfdi_uuid}/xml")
async def get_invoice_xml_endpoint(
    cfdi_uuid: str,
    download: bool = Query(default=False, description="Si true, fuerza descarga en lugar de vista previa"),
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> Response:
    """Retorna el XML del CFDI como archivo."""
    async with uow_factory() as uow:
        doc = await uow.invoices.get_pac_response_by_cfdi_uuid(cfdi_uuid)

    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factura no encontrada")

    xml_content = doc.get("cfdi_xml") or _extract_data_block(doc.get("pac_response")).get("XML")

    if not xml_content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="XML no disponible para esta factura")

    disposition = "attachment" if download else "inline"
    return Response(
        content=xml_content.encode("utf-8"),
        media_type="application/xml",
        headers={"Content-Disposition": f'{disposition}; filename="factura_{cfdi_uuid}.xml"'},
    )


# ---------------------------------------------------------------------------
# GET /v1/cfdi/{cfdi_uuid}/zip
# ---------------------------------------------------------------------------

@router.get("/{cfdi_uuid}/zip")
async def download_invoice_zip_endpoint(
    cfdi_uuid: str,
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> Response:
    """Descarga un ZIP con el XML y (si está disponible) el PDF del CFDI timbrado."""
    async with uow_factory() as uow:
        doc = await uow.invoices.get_pac_response_by_cfdi_uuid(cfdi_uuid)

    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factura no encontrada")

    xml_content = doc.get("cfdi_xml") or _extract_data_block(doc.get("pac_response")).get("XML")
    pdf_b64 = doc.get("cfdi_pdf_b64") or _extract_data_block(doc.get("pac_response")).get("PDF")

    if not xml_content and not pdf_b64:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay documentos disponibles para esta factura.",
        )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if xml_content:
            zf.writestr(f"{cfdi_uuid}.xml", xml_content.encode("utf-8"))
        if pdf_b64:
            zf.writestr(f"{cfdi_uuid}.pdf", base64.b64decode(pdf_b64))

    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="factura_{cfdi_uuid}.zip"'},
    )
