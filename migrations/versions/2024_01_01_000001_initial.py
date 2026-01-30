"""initial schema"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "2024_01_01_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column("rfc", sa.String(length=13), nullable=False, unique=True),
        sa.Column("tax_regime", sa.String(length=5), nullable=False),
        sa.Column("email", sa.String(length=255)),
        sa.Column("street", sa.String(length=120), nullable=False),
        sa.Column("exterior_number", sa.String(length=12), nullable=False),
        sa.Column("neighborhood", sa.String(length=80), nullable=False),
        sa.Column("city", sa.String(length=80), nullable=False),
        sa.Column("state", sa.String(length=50), nullable=False),
        sa.Column("country", sa.String(length=3), nullable=False, server_default="MEX"),
        sa.Column("zip_code", sa.String(length=5), nullable=False),
        sa.Column("facturify_uuid", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column("rfc", sa.String(length=13), nullable=False, unique=True),
        sa.Column("tax_regime", sa.String(length=5), nullable=False),
        sa.Column("email", sa.String(length=255)),
        sa.Column("street", sa.String(length=120), nullable=False),
        sa.Column("exterior_number", sa.String(length=12), nullable=False),
        sa.Column("neighborhood", sa.String(length=80), nullable=False),
        sa.Column("city", sa.String(length=80), nullable=False),
        sa.Column("state", sa.String(length=50), nullable=False),
        sa.Column("country", sa.String(length=3), nullable=False, server_default="MEX"),
        sa.Column("zip_code", sa.String(length=5), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("issuer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("cfdi_type", sa.String(length=16), nullable=False),
        sa.Column("complement", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("subtotal", sa.Float, nullable=False),
        sa.Column("total", sa.Float, nullable=False),
        sa.Column("cfdi_use", sa.String(length=5), nullable=False),
        sa.Column("payment_form", sa.String(length=3), nullable=False),
        sa.Column("payment_method", sa.String(length=3), nullable=False),
        sa.Column("expedition_place", sa.String(length=5), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("facturify_uuid", sa.String(length=64)),
        sa.Column("facturify_payload", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "invoice_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_key", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("quantity", sa.Float, nullable=False),
        sa.Column("unit_key", sa.String(length=10), nullable=False),
        sa.Column("unit_price", sa.Float, nullable=False),
        sa.Column("taxes", postgresql.JSONB),
    )

    op.create_table(
        "shipments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("transport_mode", sa.String(length=5), nullable=False),
        sa.Column("permit_type", sa.String(length=10), nullable=False),
        sa.Column("permit_number", sa.String(length=30), nullable=False),
        sa.Column("total_distance_km", sa.Float),
        sa.Column("total_weight_kg", sa.Float, nullable=False),
        sa.Column("vehicle_configuration", sa.String(length=10), nullable=False),
        sa.Column("vehicle_plate", sa.String(length=10), nullable=False),
        sa.Column("vehicle_permit", sa.String(length=30)),
        sa.Column("insurance_company", sa.String(length=120)),
        sa.Column("insurance_policy", sa.String(length=80)),
    )

    op.create_table(
        "shipment_locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("datetime", sa.DateTime(timezone=False), nullable=False),
        sa.Column("street", sa.String(length=120), nullable=False),
        sa.Column("exterior_number", sa.String(length=12), nullable=False),
        sa.Column("neighborhood", sa.String(length=80), nullable=False),
        sa.Column("city", sa.String(length=80), nullable=False),
        sa.Column("state", sa.String(length=50), nullable=False),
        sa.Column("country", sa.String(length=3), nullable=False),
        sa.Column("zip_code", sa.String(length=5), nullable=False),
        sa.Column("latitude", sa.Float),
        sa.Column("longitude", sa.Float),
        sa.Column("reference", sa.String(length=200)),
    )

    op.create_table(
        "shipment_goods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("product_key", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Float, nullable=False),
        sa.Column("unit_key", sa.String(length=10), nullable=False),
        sa.Column("weight_kg", sa.Float, nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("dangerous_material", sa.Boolean, server_default=sa.text("false")),
        sa.Column("dangerous_key", sa.String(length=10)),
    )

    op.create_table(
        "transport_figures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(length=4), nullable=False),
        sa.Column("rfc", sa.String(length=13), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("license", sa.String(length=20)),
        sa.Column("role_description", sa.String(length=120)),
    )


def downgrade() -> None:
    op.drop_table("transport_figures")
    op.drop_table("shipment_goods")
    op.drop_table("shipment_locations")
    op.drop_table("shipments")
    op.drop_table("invoice_items")
    op.drop_table("invoices")
    op.drop_table("clients")
    op.drop_table("companies")
