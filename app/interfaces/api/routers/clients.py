from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.application.dtos import ClientsListResponse
from app.core.exceptions import ExternalServiceError
from app.infrastructure.http.facturify_client import FacturifyClient
from app.interfaces.api.deps import get_facturify_client

router = APIRouter(prefix="/v1/clients", tags=["clients"])


@router.get(
    "",
    response_model=ClientsListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Lista de clientes obtenida exitosamente",
            "model": ClientsListResponse,
        },
        401: {"description": "No autorizado"},
        404: {"description": "Recurso no encontrado"},
        422: {"description": "Error de validación"},
        500: {"description": "Error interno del servidor"},
    },
)
async def get_clients_endpoint(
    limit: int = Query(default=50, ge=1, le=100, description="Número de registros a retornar"),
    offset: int = Query(default=0, ge=0, description="Número de registros a saltar"),
    facturify_client: FacturifyClient = Depends(get_facturify_client),
) -> ClientsListResponse:
    try:
        response = await facturify_client.get_clients(limit=limit, offset=offset)
        return ClientsListResponse(**response)
    except ExternalServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error al comunicarse con Facturify: {str(error)}"
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado: {str(error)}"
        ) from error
