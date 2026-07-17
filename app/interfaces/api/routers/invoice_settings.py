"""Configuración de serie/folio de facturación, editable desde 'Mi cuenta'."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.dtos import InvoiceSettingsRead, InvoiceSettingsUpdate
from app.interfaces.api.deps import UnitOfWorkFactory, get_uow_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/settings", tags=["settings"])


@router.get("/invoice", response_model=InvoiceSettingsRead)
async def get_invoice_settings_endpoint(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> InvoiceSettingsRead:
    async with uow_factory() as uow:
        settings = await uow.invoice_settings.get()
    return InvoiceSettingsRead(
        serie=settings.serie, next_folio=settings.next_folio, updated_at=settings.updated_at
    )


@router.put("/invoice", response_model=InvoiceSettingsRead)
async def update_invoice_settings_endpoint(
    payload: InvoiceSettingsUpdate,
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> InvoiceSettingsRead:
    async with uow_factory() as uow:
        max_folio = await uow.invoices.get_max_folio()
        if max_folio is not None and payload.next_folio <= max_folio:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"El siguiente folio debe ser mayor a {max_folio} "
                    "(último folio ya utilizado), para evitar folios duplicados."
                ),
            )
        settings = await uow.invoice_settings.update(
            serie=payload.serie, next_folio=payload.next_folio
        )

    logger.info(
        "invoice_settings actualizado: serie=%s next_folio=%s",
        settings.serie,
        settings.next_folio,
    )
    return InvoiceSettingsRead(
        serie=settings.serie, next_folio=settings.next_folio, updated_at=settings.updated_at
    )
