"""Update margin_settings default from 12% to 15%.

Revision ID: 0011_margin_15pct
Revises: 0010_pro_invoices
Create Date: 2026-06-27
"""

from alembic import op

revision = "0011_margin_15pct"
down_revision = "0010_pro_invoices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "margin_settings",
        "margin_percentage",
        server_default="15.00",
    )


def downgrade() -> None:
    op.alter_column(
        "margin_settings",
        "margin_percentage",
        server_default="12.00",
    )
