"""Store ECOPILAS Spain battery fee schedule in report_template_config.

ECOPILAS (managed by Recyclia) is the Spanish PRO for batteries.
Fees are per unit (€/Ud) or per kg (€/kg) depending on battery type and weight.

Key categories:
- Portable non-rechargeable button batteries (zinc-air, silver oxide, alkaline, lithium)
- Portable non-rechargeable non-button batteries (alkaline, carbon zinc, lithium)
- Portable rechargeable non-button batteries (NiCd, NiMh, lithium, lead acid)
- Light transport batteries (e-bikes, scooters) — 0.35 €/kg lithium, 0.015 €/kg lead
- Industrial rechargeable batteries — NiCd 0.16/kg, lithium 0.35/kg, lead 0.015/kg
- EV batteries — requires specific addendum from ECOPILAS (not self-service)

Revision ID: 0018_ecopilas_fee_schedule
Revises: 0017_pro_fee_schedules
Create Date: 2026-06-29
"""

import json
from alembic import op
import sqlalchemy as sa

revision = "0018_ecopilas_fee_schedule"
down_revision = "0017_pro_fee_schedules"
branch_labels = None
depends_on = None

ECOPILAS_ES = {
    "fee_unit": "mixed",
    "currency": "EUR",
    "effective_from": "2025-01-01",
    "joining_fee": 300.0,
    "notes": (
        "Joining fee EUR 300 (shared with ECOASIMELEC). "
        "EV battery category requires a specific addendum — contact ECOPILAS before declaring. "
        "Large renewable energy storage also requires addendum. "
        "Fees per RD 1055/2022 (batteries regulation)."
    ),
    "fee_schedule": {
        "portable_battery": {
            "button_cell_non_rechargeable": {
                "zinc_air": {"per_unit": 0.003},
                "silver_oxide": {"per_unit": 0.005},
                "alkaline_lte_8g": {"per_unit": 0.005},
                "alkaline_gt_8g": {"per_kg": 4.5},
                "lithium_lte_0_5g": {"per_kg": 4.5},
                "lithium_0_51_to_2g": {"per_unit": 0.005},
                "lithium_2_to_7g": {"per_unit": 0.011},
                "lithium_gt_7g": {"per_kg": 4.5},
                "other_button": {"per_kg": 4.5}
            },
            "button_cell_rechargeable": {
                "lithium_lte_0_5g": {"per_kg": 4.5},
                "lithium_0_51_to_2g": {"per_unit": 0.005},
                "lithium_2_to_7g": {"per_unit": 0.011},
                "lithium_gt_7g": {"per_kg": 4.5},
                "other_button": {"per_kg": 4.5}
            },
            "non_rechargeable_non_button": {
                "alkaline_lte_20g": {"per_unit": 0.004},
                "alkaline_20_to_50g": {"per_unit": 0.005},
                "alkaline_51_to_170g": {"per_unit": 0.042},
                "alkaline_gte_171g": {"per_kg": 0.5},
                "carbon_zinc_lte_20g": {"per_unit": 0.004},
                "carbon_zinc_20_to_50g": {"per_unit": 0.005},
                "carbon_zinc_51_to_170g": {"per_unit": 0.042},
                "carbon_zinc_gte_171g": {"per_kg": 0.5},
                "lithium_aaa": {"per_unit": 0.03},
                "lithium_aa": {"per_unit": 0.06},
                "lithium_lte_20g": {"per_unit": 0.06},
                "lithium_20_to_50g": {"per_unit": 0.12},
                "lithium_51_to_170g": {"per_unit": 0.14},
                "lithium_gt_170g": {"per_kg": 1.2},
                "other_non_rechargeable": {"per_kg": 0.5}
            },
            "rechargeable_non_button": {
                "nicd_lte_20g": {"per_unit": 0.018},
                "nicd_20_to_50g": {"per_unit": 0.02},
                "nicd_51_to_170g": {"per_unit": 0.05},
                "nicd_171_to_380g": {"per_unit": 0.2},
                "nicd_380_to_499g": {"per_unit": 0.3},
                "nicd_gte_500g": {"per_unit": 0.5},
                "nimh_lte_20g": {"per_unit": 0.015},
                "nimh_20_to_50g": {"per_unit": 0.019},
                "nimh_51_to_170g": {"per_unit": 0.046},
                "nimh_171_to_380g": {"per_unit": 0.175},
                "nimh_380_to_499g": {"per_unit": 0.276},
                "nimh_gte_500g": {"per_unit": 0.46},
                "lithium_lte_20g": {"per_unit": 0.015},
                "lithium_20_to_50g": {"per_unit": 0.019},
                "lithium_51_to_170g": {"per_unit": 0.046},
                "lithium_171_to_380g": {"per_unit": 0.175},
                "lithium_380_to_499g": {"per_unit": 0.276},
                "lithium_gte_500g": {"per_unit": 0.46},
                "lead_acid": {"per_kg": 0.015},
                "other_rechargeable": {"per_kg": 0.72174}
            }
        },
        "light_transport_battery": {
            "motorbike_ebike_scooter": {
                "lithium_nmc": {"per_kg": 0.35},
                "lithium_lfp": {"per_kg": 0.35},
                "lithium_other": {"per_kg": 0.35},
                "lead_acid": {"per_kg": 0.015},
                "nimh": {"per_kg": 0.35},
                "other": {"per_kg": 0.35}
            }
        },
        "industrial_battery": {
            "rechargeable": {
                "nicd": {"per_kg": 0.16},
                "lead_acid": {"per_kg": 0.015},
                "nimh": {"per_kg": 0.35},
                "lithium_nmc": {"per_kg": 0.35},
                "lithium_lfp": {"per_kg": 0.35},
                "lithium_other": {"per_kg": 0.35},
                "lithium_residential_self_supply": {"per_kg": 0.19},
                "lithium_industrial_self_supply": {"per_kg": 0.19},
                "other": {"per_kg": 0.35}
            },
            "non_rechargeable": {
                "alkaline": {"per_kg": 0.35},
                "lithium": {"per_kg": 1.2},
                "other": {"per_kg": 0.35}
            }
        },
        "ev_battery": {
            "_note": "Requires specific addendum from ECOPILAS before declaring. Contact info@ecopilas.es"
        },
        "vehicle_starting_battery": {
            "lead_acid": {"per_kg": 0.015},
            "lithium_500_to_999g": {"per_unit": 0.3},
            "lithium_gte_1000g": {"per_kg": 0.35},
            "other": {"per_kg": 0.35}
        }
    }
}


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE pro_organisations "
            "SET report_template_config = :config, updated_at = now() "
            "WHERE pro_key = :pro_key"
        ),
        {"config": json.dumps(ECOPILAS_ES), "pro_key": "ecopilas-es"},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE pro_organisations "
            "SET report_template_config = NULL, updated_at = now() "
            "WHERE pro_key = 'ecopilas-es'"
        ),
    )
