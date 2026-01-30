"""Implementacion SQLAlchemy del puerto CompanyGateway."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.repositories import CompanyGateway
from app.domain.entities import Address, Party
from app.infrastructure.orm.models import CompanyORM


class SQLAlchemyCompanyGateway(CompanyGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, company_id: UUID) -> Party | None:
        stmt = select(CompanyORM).where(CompanyORM.id == company_id)
        result = await self._session.execute(stmt)
        company = result.scalar_one_or_none()
        if company is None:
            return None
        return self._to_entity(company)

    async def get_by_rfc(self, rfc: str) -> Party | None:
        stmt = select(CompanyORM).where(CompanyORM.rfc == rfc)
        result = await self._session.execute(stmt)
        company = result.scalar_one_or_none()
        if company is None:
            return None
        return self._to_entity(company)

    async def create(self, party: Party) -> Party:
        company = CompanyORM(
            legal_name=party.legal_name,
            rfc=party.rfc,
            tax_regime=party.tax_regime,
            email=party.email,
            street=party.address.street,
            exterior_number=party.address.exterior_number,
            neighborhood=party.address.neighborhood,
            city=party.address.city,
            state=party.address.state,
            country=party.address.country,
            zip_code=party.address.zip_code,
            facturify_uuid=party.external_uuid or "",
        )
        self._session.add(company)
        await self._session.flush()
        await self._session.refresh(company)
        return self._to_entity(company)

    def _to_entity(self, company: CompanyORM) -> Party:
        address = Address(
            street=company.street,
            exterior_number=company.exterior_number,
            neighborhood=company.neighborhood,
            city=company.city,
            state=company.state,
            country=company.country,
            zip_code=company.zip_code,
        )
        return Party(
            id=company.id,
            legal_name=company.legal_name,
            rfc=company.rfc,
            tax_regime=company.tax_regime,
            email=company.email,
            address=address,
            external_uuid=company.facturify_uuid,
        )
