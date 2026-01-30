"""API endpoints for Facturify empresa management."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.infrastructure.http.facturify_empresa_client import (
    FacturifyEmpresaError,
    get_facturify_empresa_client,
)
from app.interfaces.api.schemas.facturify_empresa import (
    Empresa,
    EmpresaListResponse,
    EmpresaResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/facturify/empresa", tags=["Facturify Empresa"])


@router.get(
    "/",
    response_model=EmpresaListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all empresas",
    description="Retrieves all empresas (companies) from Facturify.",
)
async def get_empresas() -> EmpresaListResponse:
    """Get all empresas from Facturify."""
    try:
        client = await get_facturify_empresa_client()
        response_data = await client.get_empresas()
        return EmpresaListResponse(**response_data)
    except FacturifyEmpresaError as e:
        logger.error(f"Failed to get empresas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error getting empresas: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/rfc/{rfc}",
    response_model=EmpresaResponse,
    status_code=status.HTTP_200_OK,
    summary="Get empresa by RFC",
    description="Retrieves a specific empresa by RFC (e.g., ALO161103C77).",
)
async def get_empresa_by_rfc(rfc: str) -> EmpresaResponse:
    """Get empresa by RFC."""
    try:
        client = await get_facturify_empresa_client()
        empresa = await client.get_empresa_by_rfc(rfc)
        
        if not empresa:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Empresa with RFC '{rfc}' not found",
            )
        
        return EmpresaResponse(data=empresa)
    except HTTPException:
        raise
    except FacturifyEmpresaError as e:
        logger.error(f"Failed to get empresa by RFC {rfc}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error getting empresa by RFC {rfc}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
