"""Agrega request_snapshot (JSON del formulario UI) para precargar facturas futuras.

Revision ID: 2026_07_21_000001
Revises: 2026_07_17_000001
Create Date: 2026-07-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "2026_07_21_000001"
down_revision = "2026_07_17_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column("request_snapshot", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("invoices", "request_snapshot")
