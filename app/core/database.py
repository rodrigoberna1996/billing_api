"""Configuracion de SQLAlchemy asincronico."""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


_settings = get_settings()
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Inicializa (una unica vez) el engine asincronico."""

    global _engine, _session_factory  # noqa: PLW0603 - patron singleton controlado
    if _engine is None:
        _engine = create_async_engine(_settings.database_url, echo=_settings.db_echo, future=True)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = get_engine()
    assert _session_factory is not None  # mypy-friendly, se monta junto con el engine
    return _session_factory


async def dispose_engine() -> None:
    if _engine is not None:
        await _engine.dispose()


async def session_scope() -> AsyncIterator[AsyncSession]:
    """Sirve como dependency override en tests o scripts."""

    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
        await session.commit()
    except Exception:  # pragma: no cover - repropaga para FastAPI
        await session.rollback()
        raise
    finally:
        await session.close()
