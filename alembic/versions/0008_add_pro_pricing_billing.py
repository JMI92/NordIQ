"""Add PRO pricing, margin settings and extend invoices for automated billing

Revision ID: 0008_add_pro_pricing_billing
Revises: 0007
Create Date: 2026-06-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0008_add_pro_pricing_billing"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PRO pricing table
    op.create_table(
        "pro_pricing",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pro_id", UUID(as_uuid=True), sa.ForeignKey("pro_organisations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("waste_stream", sa.String(50), nullable=False),
        sa.Column("fee_type", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(12, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint("pro_id", "waste_stream", "fee_type", "effective_date", name="uq_pro_pricing"),
    )
    op.create_index("ix_pro_pricing_pro_id", "pro_pricing", ["pro_id"])
    op.create_index("ix_pro_pricing_waste_stream", "pro_pricing", ["waste_stream"])
    op.create_index("ix_pro_pricing_fee_type", "pro_pricing", ["fee_type"])

    # Margin settings table
    op.create_table(
        "margin_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pro_id", UUID(as_uuid=True), sa.ForeignKey("pro_organisations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("margin_percentage", sa.Numeric(5, 2), nullable=False, server_default="12.00"),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_margin_settings_pro_id", "margin_settings", ["pro_id"])

    # Extend invoices table
    op.add_column("invoices", sa.Column("invoice_type", sa.String(20), nullable=False, server_default="manual"))
    op.add_column("invoices", sa.Column("service_fee", sa.Numeric(12, 2), nullable=False, server_default="30.00"))
    op.add_column("invoices", sa.Column("period_start", sa.Date, nullable=True))
    op.add_column("invoices", sa.Column("period_end", sa.Date, nullable=True))
    op.add_column("invoices", sa.Column("accounting_ref", sa.String(100), nullable=True))
    op.add_column("invoices", sa.Column("accounting_exported_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_invoices_invoice_type", "invoices", ["invoice_type"])


def downgrade() -> None:
    op.drop_index("ix_invoices_invoice_type", "invoices")
    op.drop_column("invoices", "accounting_exported_at")
    op.drop_column("invoices", "accounting_ref")
    op.drop_column("invoices", "period_end")
    op.drop_column("invoices", "period_start")
    op.drop_column("invoices", "service_fee")
    op.drop_column("invoices", "invoice_type")

    op.drop_index("ix_margin_settings_pro_id", "margin_settings")
    op.drop_table("margin_settings")

    op.drop_index("ix_pro_pricing_fee_type", "pro_pricing")
    op.drop_index("ix_pro_pricing_waste_stream", "pro_pricing")
    op.drop_index("ix_pro_pricing_pro_id", "pro_pricing")
    op.drop_table("pro_pricing")
