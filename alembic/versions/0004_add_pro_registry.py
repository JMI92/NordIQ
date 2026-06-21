"""add PRO registry and customer PRO registrations

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pro_organisations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("country_code", sa.String(3), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("pro_key", sa.String(50), nullable=False, unique=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("portal_url", sa.String(500), nullable=True),
        sa.Column("api_endpoint", sa.String(500), nullable=True),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("contact_phone", sa.String(50), nullable=True),
        sa.Column("reporting_deadline_notes", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pro_organisations_country_code", "pro_organisations", ["country_code"])
    op.create_index("ix_pro_organisations_category", "pro_organisations", ["category"])
    op.create_index("ix_pro_organisations_pro_key", "pro_organisations", ["pro_key"])

    op.create_table(
        "customer_pro_registrations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pro_id", UUID(as_uuid=True), sa.ForeignKey("pro_organisations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("registration_number", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("contract_start", sa.Date, nullable=True),
        sa.Column("contract_end", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_customer_pro_registrations_customer_id", "customer_pro_registrations", ["customer_id"])
    op.create_index("ix_customer_pro_registrations_pro_id", "customer_pro_registrations", ["pro_id"])
    op.create_index("ix_customer_pro_registrations_status", "customer_pro_registrations", ["status"])


def downgrade() -> None:
    op.drop_table("customer_pro_registrations")
    op.drop_table("pro_organisations")
