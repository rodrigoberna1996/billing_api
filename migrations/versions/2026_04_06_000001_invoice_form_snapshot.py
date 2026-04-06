"""Add form_snapshot JSONB to invoices for template reload after timbrado.

Revision ID: 2026_04_06_000001
Revises: 2026_01_29_000001
Create Date: 2026-04-06 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "2026_04_06_000001"
down_revision = "2026_01_29_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column("form_snapshot", postgresql.JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("invoices", "form_snapshot")
