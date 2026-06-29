"""Add WEEE/battery classification fields to products for EPR fee calculation.

These fields are required to correctly map products to PRO fee schedules:
- weee_category: maps product to the correct fee schedule row
- product_use_type: household vs commercial (different rates in AT, ES)
- largest_dimension_cm: determines >50cm / ≤50cm fee bracket (NL, ES)
- battery_chemistry: determines battery fee row (NL, AT)
- battery_weight_grams: per-unit battery weight for fee calculation (NL)

Revision ID: 0016_weee_product_fields
Revises: 0015_seed_stichting_open
Create Date: 2026-06-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0016_weee_product_fields"
down_revision = "0015_seed_stichting_open"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # WEEE fee schedule category — determines which row in each PRO's fee table to use
    # Values: cooling | display_screen | lamp | large_appliance | small_appliance |
    #         small_it_telecom | photovoltaic | ebike | industrial_battery |
    #         ev_battery | portable_battery | light_transport_battery
    op.add_column(
        "products",
        sa.Column("weee_category", sa.String(50), nullable=True),
    )
    op.create_index("ix_products_weee_category", "products", ["weee_category"])

    # household or commercial — affects UFH (AT) and ECOASIMELEC (ES) rates
    op.add_column(
        "products",
        sa.Column("product_use_type", sa.String(20), nullable=True,
                  server_default="household"),
    )

    # Largest external dimension in cm — determines >50cm / ≤50cm bracket (NL, ES)
    op.add_column(
        "products",
        sa.Column("largest_dimension_cm", sa.Numeric(7, 1), nullable=True),
    )

    # Battery chemistry — determines fee row for battery products
    # Values: lithium_ion | lithium_tcl | lead_acid | nimh | other
    op.add_column(
        "products",
        sa.Column("battery_chemistry", sa.String(30), nullable=True),
    )

    # Per-unit battery weight in grams — used for NL Stichting OPEN per-battery fee
    op.add_column(
        "products",
        sa.Column("battery_weight_grams", sa.Numeric(10, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_index("ix_products_weee_category", table_name="products")
    op.drop_column("products", "weee_category")
    op.drop_column("products", "product_use_type")
    op.drop_column("products", "largest_dimension_cm")
    op.drop_column("products", "battery_chemistry")
    op.drop_column("products", "battery_weight_grams")
