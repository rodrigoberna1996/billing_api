"""Pruebas de GET/PUT /v1/settings/invoice — serie y folio editables desde 'Mi cuenta'."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import HTTPException

from app.domain.entities import InvoiceSettings
from app.interfaces.api.routers.invoice_settings import (
    get_invoice_settings_endpoint,
    update_invoice_settings_endpoint,
)


class _FakeInvoiceSettingsRepo:
    def __init__(self, settings: InvoiceSettings) -> None:
        self.settings = settings
        self.update_calls: list[tuple[str, int]] = []

    async def get(self) -> InvoiceSettings:
        return self.settings

    async def update(self, serie: str, next_folio: int) -> InvoiceSettings:
        self.update_calls.append((serie, next_folio))
        self.settings = InvoiceSettings(
            serie=serie, next_folio=next_folio, updated_at=datetime.now(timezone.utc)
        )
        return self.settings


class _FakeInvoiceRepo:
    def __init__(self, max_folio: int | None) -> None:
        self.max_folio = max_folio

    async def get_max_folio(self) -> int | None:
        return self.max_folio


class _FakeUow:
    def __init__(self, invoice_settings: _FakeInvoiceSettingsRepo, invoices: _FakeInvoiceRepo) -> None:
        self.invoice_settings = invoice_settings
        self.invoices = invoices

    async def __aenter__(self) -> "_FakeUow":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None


def _uow_factory(settings_repo: _FakeInvoiceSettingsRepo, max_folio: int | None = None):
    def factory() -> _FakeUow:
        return _FakeUow(settings_repo, _FakeInvoiceRepo(max_folio))

    return factory


async def test_get_invoice_settings_returns_current_values() -> None:
    repo = _FakeInvoiceSettingsRepo(InvoiceSettings(serie="CCP", next_folio=4012))

    result = await get_invoice_settings_endpoint(uow_factory=_uow_factory(repo))

    assert result.serie == "CCP"
    assert result.next_folio == 4012


async def test_update_invoice_settings_updates_serie_and_folio() -> None:
    from app.application.dtos import InvoiceSettingsUpdate

    repo = _FakeInvoiceSettingsRepo(InvoiceSettings(serie="CCP", next_folio=4012))

    result = await update_invoice_settings_endpoint(
        payload=InvoiceSettingsUpdate(serie="ccp2", next_folio=5000),
        uow_factory=_uow_factory(repo, max_folio=4011),
    )

    assert result.serie == "CCP2"
    assert result.next_folio == 5000
    assert repo.update_calls == [("CCP2", 5000)]


async def test_update_invoice_settings_rejects_folio_not_greater_than_max_used() -> None:
    from app.application.dtos import InvoiceSettingsUpdate

    repo = _FakeInvoiceSettingsRepo(InvoiceSettings(serie="CCP", next_folio=4012))

    with pytest.raises(HTTPException) as exc_info:
        await update_invoice_settings_endpoint(
            payload=InvoiceSettingsUpdate(serie="CCP", next_folio=4000),
            uow_factory=_uow_factory(repo, max_folio=4011),
        )

    assert exc_info.value.status_code == 422
    assert repo.update_calls == []


async def test_update_invoice_settings_allows_any_folio_when_none_used_yet() -> None:
    from app.application.dtos import InvoiceSettingsUpdate

    repo = _FakeInvoiceSettingsRepo(InvoiceSettings(serie="CCP", next_folio=4000))

    result = await update_invoice_settings_endpoint(
        payload=InvoiceSettingsUpdate(serie="CCP", next_folio=1),
        uow_factory=_uow_factory(repo, max_folio=None),
    )

    assert result.next_folio == 1
