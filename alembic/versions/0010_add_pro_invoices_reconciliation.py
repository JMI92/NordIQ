"""Add pro_invoices table for incoming PRO invoices and margin reconciliation.

Revision ID: 0010_add_pro_invoices_reconciliation
Revises: 0009_add_pro_report_format
Create Date: 2026-06-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0010_add_pro_invoices_reconciliation"
down_revision = "0009_add_pro_report_format"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pro_invoices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pro_id", UUID(as_uuid=True), sa.ForeignKey("pro_organisations.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("customer_invoice_id", UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("pro_invoice_number", sa.String(100), nullable=True),
        sa.Column("invoice_type", sa.String(20), nullable=False, server_default="monthly", index=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("period_start", sa.Date, nullable=True),
        sa.Column("period_end", sa.Date, nullable=True),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="received", index=True),
        sa.Column("received_at", sa.Date, nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("line_items", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pro_invoices_customer_period", "pro_invoices", ["customer_id", "period_start", "period_end"])


def downgrade() -> None:
    op.drop_index("ix_pro_invoices_customer_period", table_name="pro_invoices")
    op.drop_table("pro_invoices")
