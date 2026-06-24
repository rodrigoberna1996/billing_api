"""Endpoints para consultar receptores (clientes) almacenados localmente."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.infrastructure.orm.models import ClientORM

router = APIRouter(prefix="/v1/clients", tags=["clients"])


async def _get_session() -> AsyncSession:
    factory = get_session_factory()
    async with factory() as session:
        yield session


@router.get("", status_code=status.HTTP_200_OK)
async def get_clients_endpoint(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    rfc: str | None = Query(default=None, description="Filtrar por RFC exacto"),
    session: AsyncSession = Depends(_get_session),
) -> dict:
    """Lista los receptores almacenados en la DB local."""
    stmt = select(ClientORM)
    count_stmt = select(func.count()).select_from(ClientORM)

    if rfc:
        stmt = stmt.where(ClientORM.rfc == rfc.upper())
        count_stmt = count_stmt.where(ClientORM.rfc == rfc.upper())

    stmt = stmt.limit(limit).offset(offset).order_by(ClientORM.created_at.desc())

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt)).scalars().all()

    data = [
        {
            "id": str(c.id),
            "legal_name": c.legal_name,
            "rfc": c.rfc,
            "tax_regime": c.tax_regime,
            "email": c.email,
            "zip_code": c.zip_code,
            "state": c.state,
            "country": c.country,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in rows
    ]

    return {
        "data": data,
        "meta": {
            "total": total,
            "count": len(data),
            "per_page": limit,
            "offset": offset,
        },
    }
