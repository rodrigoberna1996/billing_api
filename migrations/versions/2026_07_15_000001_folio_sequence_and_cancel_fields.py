"""Secuencia de folio consecutivo (desde 4000) + campos de cancelación de CFDI.

Revision ID: 2026_07_15_000001
Revises: 2026_06_19_000001
Create Date: 2026-07-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "2026_07_15_000001"
down_revision = "2026_06_19_000001"
branch_labels = None
depends_on = None

FOLIO_SEQ_NAME = "invoices_folio_seq"
FOLIO_SEQ_START = 4000


def upgrade() -> None:
    op.execute(
        f"CREATE SEQUENCE IF NOT EXISTS {FOLIO_SEQ_NAME} "
        f"START WITH {FOLIO_SEQ_START} INCREMENT BY 1 OWNED BY invoices.folio"
    )

    op.add_column("invoices", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invoices", sa.Column("cancel_motivo", sa.String(2), nullable=True))
    op.add_column("invoices", sa.Column("cancel_response", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("invoices", "cancel_response")
    op.drop_column("invoices", "cancel_motivo")
    op.drop_column("invoices", "cancelled_at")
    op.execute(f"DROP SEQUENCE IF EXISTS {FOLIO_SEQ_NAME}")
