"""Add report_format and report_template_config to pro_organisations.

Revision ID: 0009_add_pro_report_format
Revises: 0008_add_pro_pricing_billing
Create Date: 2026-06-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0009_add_pro_report_format"
down_revision = "0008_add_pro_pricing_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pro_organisations",
        sa.Column("report_format", sa.String(20), nullable=False, server_default="generic_csv"),
    )
    op.add_column(
        "pro_organisations",
        sa.Column("report_template_config", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pro_organisations", "report_template_config")
    op.drop_column("pro_organisations", "report_format")
