"""Repositorio de clientes (receptores)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.repositories import ClientGateway
from app.domain.entities import Address, Party
from app.infrastructure.orm.models import ClientORM


class SQLAlchemyClientGateway(ClientGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_rfc(self, rfc: str) -> Party | None:
        stmt = select(ClientORM).where(ClientORM.rfc == rfc)
        result = await self._session.execute(stmt)
        client = result.scalar_one_or_none()
        if client is None:
            return None
        return self._to_party(client)

    async def upsert(self, party: Party) -> Party:
        stmt = select(ClientORM).where(ClientORM.rfc == party.rfc)
        result = await self._session.execute(stmt)
        client = result.scalar_one_or_none()
        if client is None:
            client = ClientORM(
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
            )
            self._session.add(client)
        else:
            client.legal_name = party.legal_name
            client.tax_regime = party.tax_regime
            client.email = party.email
            client.street = party.address.street
            client.exterior_number = party.address.exterior_number
            client.neighborhood = party.address.neighborhood
            client.city = party.address.city
            client.state = party.address.state
            client.country = party.address.country
            client.zip_code = party.address.zip_code
        await self._session.flush()
        return self._to_party(client)

    def _to_party(self, client: ClientORM) -> Party:
        return Party(
            id=client.id,
            legal_name=client.legal_name,
            rfc=client.rfc,
            tax_regime=client.tax_regime,
            email=client.email,
            address=Address(
                street=client.street,
                exterior_number=client.exterior_number,
                neighborhood=client.neighborhood,
                city=client.city,
                state=client.state,
                country=client.country,
                zip_code=client.zip_code,
            ),
        )
