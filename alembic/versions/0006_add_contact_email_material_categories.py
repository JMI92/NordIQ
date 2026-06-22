"""add contact_email to customers and material_categories to customer_pro_registrations

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("contact_email", sa.String(255), nullable=True))
    op.add_column(
        "customer_pro_registrations",
        sa.Column("material_categories", JSONB, nullable=True, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("customer_pro_registrations", "material_categories")
    op.drop_column("customers", "contact_email")
