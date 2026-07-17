"""Tabla invoice_settings: serie/folio editables desde 'Mi cuenta' (fila única id=1).

Se siembra con el valor equivalente al siguiente valor de invoices_folio_seq,
sin consumirlo, para no perder continuidad en el conteo ya emitido.

Revision ID: 2026_07_17_000001
Revises: 2026_07_15_000001
Create Date: 2026-07-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "2026_07_17_000001"
down_revision = "2026_07_15_000001"
branch_labels = None
depends_on = None

DEFAULT_SERIE = "CCP"


def upgrade() -> None:
    op.create_table(
        "invoice_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("serie", sa.String(10), nullable=False, server_default=DEFAULT_SERIE),
        sa.Column("next_folio", sa.Integer(), nullable=False, server_default="4000"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.execute(
        f"""
        INSERT INTO invoice_settings (id, serie, next_folio)
        SELECT 1, '{DEFAULT_SERIE}',
               CASE WHEN is_called THEN last_value + 1 ELSE last_value END
        FROM invoices_folio_seq
        ON CONFLICT (id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("invoice_settings")
