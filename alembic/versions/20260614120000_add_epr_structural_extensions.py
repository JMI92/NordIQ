"""Add EPR structural extensions: eco-modulation, fixed fees, SUP, packaging BOM, PPWR.

Revision ID: 20260614120000
Revises: 0002
Create Date: 2026-06-14 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260614120000"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to epr_rates
    op.add_column(
        "epr_rates",
        sa.Column("fixed_annual_fee_eur", sa.Numeric(18, 4), nullable=True),
    )
    op.add_column(
        "epr_rates",
        sa.Column(
            "eco_modulation_factor",
            sa.Numeric(8, 4),
            nullable=False,
            server_default="1.0000",
        ),
    )
    op.add_column(
        "epr_rates",
        sa.Column("packaging_stream", sa.String(20), nullable=True),
    )
    op.add_column(
        "epr_rates",
        sa.Column(
            "is_sup_surcharge",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "epr_rates",
        sa.Column("ppwr_effective_from", sa.Date(), nullable=True),
    )

    # Create packaging_components table
    op.create_table(
        "packaging_components",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "customer_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("sku", sa.String(255), nullable=False),
        sa.Column("product_name", sa.String(500), nullable=True),
        sa.Column("component_name", sa.String(255), nullable=False),
        sa.Column("material_type", sa.String(50), nullable=False),
        sa.Column(
            "packaging_stream",
            sa.String(20),
            nullable=False,
            server_default="household",
        ),
        sa.Column("weight_grams", sa.Numeric(12, 4), nullable=False),
        sa.Column(
            "is_recyclable",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("recyclability_class", sa.String(50), nullable=True),
        sa.Column(
            "is_single_use_plastic",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "is_reusable",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
    )
    op.create_index("ix_packaging_components_customer_id", "packaging_components", ["customer_id"])
    op.create_index("ix_packaging_components_sku", "packaging_components", ["sku"])


def downgrade() -> None:
    op.drop_index("ix_packaging_components_sku", table_name="packaging_components")
    op.drop_index("ix_packaging_components_customer_id", table_name="packaging_components")
    op.drop_table("packaging_components")

    op.drop_column("epr_rates", "ppwr_effective_from")
    op.drop_column("epr_rates", "is_sup_surcharge")
    op.drop_column("epr_rates", "packaging_stream")
    op.drop_column("epr_rates", "eco_modulation_factor")
    op.drop_column("epr_rates", "fixed_annual_fee_eur")
