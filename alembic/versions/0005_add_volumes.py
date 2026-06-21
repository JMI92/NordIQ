"""add product_material_compositions and monthly_sales_volumes tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_material_compositions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("material_type", sa.String(50), nullable=False),
        sa.Column("is_packaging", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("weight_per_unit_kg", sa.Numeric(18, 6), nullable=False),
        sa.Column("packaging_stream", sa.String(20), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("product_id", "material_type", "is_packaging", name="uq_pmc_product_material_packaging"),
    )
    op.create_index("ix_product_material_compositions_product_id", "product_material_compositions", ["product_id"])

    op.create_table(
        "monthly_sales_volumes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("month", sa.Integer, nullable=False),
        sa.Column("units_sold", sa.Numeric(18, 2), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("customer_id", "product_id", "year", "month", name="uq_msv_customer_product_period"),
    )
    op.create_index("ix_monthly_sales_volumes_customer_id", "monthly_sales_volumes", ["customer_id"])
    op.create_index("ix_monthly_sales_volumes_product_id", "monthly_sales_volumes", ["product_id"])


def downgrade() -> None:
    op.drop_table("monthly_sales_volumes")
    op.drop_table("product_material_compositions")
