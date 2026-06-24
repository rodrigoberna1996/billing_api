"""Schema inicial limpio — FacturaloPlus + relacion viajes.

Revision ID: 2026_06_19_000001
Revises:
Create Date: 2026-06-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "2026_06_19_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # clients — receptores / clientes de las facturas
    # ------------------------------------------------------------------
    op.create_table(
        "clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("rfc", sa.String(13), nullable=False),
        sa.Column("tax_regime", sa.String(5), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("street", sa.String(120), nullable=False),
        sa.Column("exterior_number", sa.String(12), nullable=False),
        sa.Column("neighborhood", sa.String(80), nullable=False),
        sa.Column("city", sa.String(80), nullable=False),
        sa.Column("state", sa.String(50), nullable=False),
        sa.Column("country", sa.String(3), nullable=False, server_default="MEX"),
        sa.Column("zip_code", sa.String(5), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_clients_rfc", "clients", ["rfc"], unique=True)

    # ------------------------------------------------------------------
    # invoices — facturas CFDI (carta porte)
    # ------------------------------------------------------------------
    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "recipient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("clients.id"),
            nullable=False,
        ),
        sa.Column("cfdi_type", sa.String(16), nullable=False),
        sa.Column("complement", sa.String(32), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("subtotal", sa.Float(), nullable=False),
        sa.Column("total", sa.Float(), nullable=False),
        sa.Column("cfdi_use", sa.String(5), nullable=False),
        sa.Column("payment_form", sa.String(3), nullable=True),
        sa.Column("payment_method", sa.String(3), nullable=True),
        sa.Column("expedition_place", sa.String(5), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        # UUID del CFDI timbrado por el SAT (único por factura)
        sa.Column("cfdi_uuid", sa.String(64), nullable=True),
        # Respuesta completa del PAC (JSON)
        sa.Column("pac_response", postgresql.JSONB(), nullable=True),
        # Documentos del CFDI almacenados directamente
        sa.Column("cfdi_xml", sa.Text(), nullable=True),
        sa.Column("cfdi_pdf_b64", sa.Text(), nullable=True),
        # Referencia al viaje en adrh_logistics (sin FK — distinta DB)
        sa.Column("trip_id", sa.Integer(), nullable=True),
        # Datos de folio/serie
        sa.Column("serie", sa.String(10), nullable=True),
        sa.Column("folio", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(20), nullable=True),
        # Snapshot del formulario SAT enviado al PAC
        sa.Column("form_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_invoices_recipient_id", "invoices", ["recipient_id"])
    op.create_index("ix_invoices_cfdi_uuid", "invoices", ["cfdi_uuid"], unique=True)
    op.create_index("ix_invoices_trip_id", "invoices", ["trip_id"])


def downgrade() -> None:
    op.drop_table("invoices")
    op.drop_table("clients")
