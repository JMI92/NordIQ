"""Seed initial Nordic EPR rates and 2024 reporting deadlines.

Rates are sourced from Nordic PRO published fee schedules.
All rates are indicative — update via the epr_rates table when regulations change.

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-01 00:00:01.000000
"""
from typing import Sequence, Union
import uuid
from datetime import date

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Indicative Nordic packaging EPR rates (EUR/kg) — valid from 2024-01-01
# Sources: Finnish Packaging Producers Ltd (PYR), Förpacknings- och Tidningsinsamlingen (FTI SE),
#          Grønt Punkt Norge, Dansk Retursystem / Emballageafgiftsloven
NORDIC_PACKAGING_RATES = [
    # (country_code, material_type, rate_per_kg, currency, regulation_reference)
    ("FI", "plastic",     0.45, "EUR", "FI Packaging Producers Ltd 2024 fee schedule"),
    ("FI", "paper",       0.08, "EUR", "FI Packaging Producers Ltd 2024 fee schedule"),
    ("FI", "glass",       0.06, "EUR", "FI Packaging Producers Ltd 2024 fee schedule"),
    ("FI", "metal",       0.12, "EUR", "FI Packaging Producers Ltd 2024 fee schedule"),
    ("FI", "wood",        0.04, "EUR", "FI Packaging Producers Ltd 2024 fee schedule"),
    ("FI", "other",       0.20, "EUR", "FI Packaging Producers Ltd 2024 fee schedule"),
    ("SE", "plastic",     0.50, "SEK", "FTI SE 2024 fee schedule"),
    ("SE", "paper",       0.10, "SEK", "FTI SE 2024 fee schedule"),
    ("SE", "glass",       0.07, "SEK", "FTI SE 2024 fee schedule"),
    ("SE", "metal",       0.15, "SEK", "FTI SE 2024 fee schedule"),
    ("SE", "wood",        0.05, "SEK", "FTI SE 2024 fee schedule"),
    ("SE", "other",       0.25, "SEK", "FTI SE 2024 fee schedule"),
    ("NO", "plastic",     5.20, "NOK", "Grønt Punkt Norge 2024 fee schedule"),
    ("NO", "paper",       0.80, "NOK", "Grønt Punkt Norge 2024 fee schedule"),
    ("NO", "glass",       0.60, "NOK", "Grønt Punkt Norge 2024 fee schedule"),
    ("NO", "metal",       1.20, "NOK", "Grønt Punkt Norge 2024 fee schedule"),
    ("NO", "wood",        0.40, "NOK", "Grønt Punkt Norge 2024 fee schedule"),
    ("NO", "other",       2.50, "NOK", "Grønt Punkt Norge 2024 fee schedule"),
    ("DK", "plastic",     3.50, "DKK", "Emballageafgiftsloven 2024"),
    ("DK", "paper",       0.60, "DKK", "Emballageafgiftsloven 2024"),
    ("DK", "glass",       0.45, "DKK", "Emballageafgiftsloven 2024"),
    ("DK", "metal",       0.90, "DKK", "Emballageafgiftsloven 2024"),
    ("DK", "wood",        0.30, "DKK", "Emballageafgiftsloven 2024"),
    ("DK", "other",       1.80, "DKK", "Emballageafgiftsloven 2024"),
]

# 2024 annual reporting deadlines for Nordic packaging
NORDIC_DEADLINES = [
    # (country_code, reporting_period_start, reporting_period_end, submission_deadline, pro_id)
    ("FI", date(2024, 1, 1), date(2024, 12, 31), date(2025, 3, 31), "nordic_pro_fi"),
    ("SE", date(2024, 1, 1), date(2024, 12, 31), date(2025, 3, 31), "nordic_pro_se"),
    ("NO", date(2024, 1, 1), date(2024, 12, 31), date(2025, 4, 30), "nordic_pro_no"),
    ("DK", date(2024, 1, 1), date(2024, 12, 31), date(2025, 3, 15), "nordic_pro_dk"),
]


def upgrade() -> None:
    epr_rates = sa.table(
        "epr_rates",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("country_code", sa.String),
        sa.column("product_category", sa.String),
        sa.column("material_type", sa.String),
        sa.column("rate_per_kg", sa.Numeric),
        sa.column("currency", sa.String),
        sa.column("valid_from", sa.Date),
        sa.column("valid_to", sa.Date),
        sa.column("regulation_reference", sa.String),
    )
    op.bulk_insert(
        epr_rates,
        [
            {
                "id": uuid.uuid4(),
                "country_code": country,
                "product_category": "packaging",
                "material_type": material,
                "rate_per_kg": rate,
                "currency": currency,
                "valid_from": date(2024, 1, 1),
                "valid_to": None,
                "regulation_reference": ref,
            }
            for country, material, rate, currency, ref in NORDIC_PACKAGING_RATES
        ],
    )

    reporting_deadlines = sa.table(
        "reporting_deadlines",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("country_code", sa.String),
        sa.column("product_category", sa.String),
        sa.column("reporting_period_start", sa.Date),
        sa.column("reporting_period_end", sa.Date),
        sa.column("submission_deadline", sa.Date),
        sa.column("pro_id", sa.String),
        sa.column("notes", sa.String),
    )
    op.bulk_insert(
        reporting_deadlines,
        [
            {
                "id": uuid.uuid4(),
                "country_code": country,
                "product_category": "packaging",
                "reporting_period_start": period_start,
                "reporting_period_end": period_end,
                "submission_deadline": deadline,
                "pro_id": pro_id,
                "notes": "Annual packaging EPR report",
            }
            for country, period_start, period_end, deadline, pro_id in NORDIC_DEADLINES
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM reporting_deadlines WHERE pro_id LIKE 'nordic_pro_%'")
    op.execute(
        "DELETE FROM epr_rates WHERE country_code IN ('FI','SE','NO','DK') "
        "AND product_category = 'packaging' AND valid_from = '2024-01-01'"
    )
