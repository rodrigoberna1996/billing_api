"""Make issuer_id nullable and add facturify fields to invoices table.

Revision ID: 2026_01_29_000001
Revises: 2024_01_01_000001
Create Date: 2026-01-29 00:54:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2026_01_29_000001'
down_revision = '2024_01_01_000001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make issuer_id nullable
    op.alter_column('invoices', 'issuer_id', nullable=True)
    
    # Add facturify fields
    op.add_column("invoices", sa.Column("serie", sa.String(length=10), nullable=True))
    op.add_column("invoices", sa.Column("folio", sa.Integer, nullable=True))
    op.add_column("invoices", sa.Column("factura_id", sa.String(length=50), nullable=True))
    op.add_column("invoices", sa.Column("provider", sa.String(length=10), nullable=True))


def downgrade() -> None:
    # Remove facturify fields
    op.drop_column("invoices", "provider")
    op.drop_column("invoices", "factura_id")
    op.drop_column("invoices", "folio")
    op.drop_column("invoices", "serie")
    
    # Make issuer_id not nullable again
    op.alter_column('invoices', 'issuer_id', nullable=False)
