"""Store PRO fee schedules in report_template_config for AT, ES, NL.

Fee schedules are stored as structured JSON so the calculator can look up
the correct rate for any product without hardcoding values in application code.

Structure per PRO:
{
  "fee_schedule": {
    "<weee_category>": {
      "household": { "<bracket>": <rate> },   // AT uses weight brackets (€/piece)
      "commercial": { "<bracket>": <rate> }   // NL/ES use kg or piece directly
    }
  },
  "fee_unit": "per_piece" | "per_kg",
  "currency": "EUR",
  "effective_from": "2026-01-01",
  "min_annual_fee": <float>,   // where applicable
  "notes": "..."
}

Revision ID: 0017_pro_fee_schedules
Revises: 0016_weee_product_fields
Create Date: 2026-06-29
"""

import json
from alembic import op
import sqlalchemy as sa

revision = "0017_pro_fee_schedules"
down_revision = "0016_weee_product_fields"
branch_labels = None
depends_on = None

# ---------------------------------------------------------------------------
# UFH Austria — Household fee schedule (€/piece, weight brackets)
# ---------------------------------------------------------------------------
UFH_AT_HOUSEHOLD = {
    "fee_unit": "per_piece",
    "currency": "EUR",
    "effective_from": "2026-01-01",
    "min_annual_fee": 160.0,
    "vat_rate": 0.20,
    "early_payment_discount": 0.03,
    "notes": "Annual minimum EUR 160 excl. VAT. 3% discount if paid within 14 days.",
    "fee_schedule": {
        "large_appliance": {
            "household": {
                "lte_6kg": 0.05,
                "6_to_30kg": 0.12,
                "gt_30kg": 0.50,
                "luminaires": 0.07
            }
        },
        "cooling": {
            "household": {
                "lte_45kg": 6.90,
                "gt_45kg": 10.00,
                "heat_pump_fixed_ac": 7.60
            }
        },
        "display_screen": {
            "household": {
                "lte_10kg": 1.48,
                "10_to_25kg": 5.80,
                "gt_25kg": 9.61
            }
        },
        "small_appliance": {
            "household": {
                "lte_0_1kg": 0.01,
                "0_1_to_0_5kg": 0.01,
                "0_5_to_3kg": 0.05,
                "gt_3kg": 0.20,
                "luminaires": 0.06
            }
        },
        "small_it_telecom": {
            "household": {
                "lte_0_1kg": 0.01,
                "0_1_to_0_5kg": 0.01,
                "0_5_to_3kg": 0.06,
                "gt_3kg": 0.24
            }
        },
        "lamp": {
            "household": {
                "lte_0_04kg": 0.12,
                "gt_0_04kg": 0.26
            }
        },
        "portable_battery": {
            "household": {
                "lithium_ion": 0.70,
                "other": 0.69
            },
            "fee_unit": "per_kg"
        },
        "light_transport_battery": {
            "household": {
                "lithium_ion": 0.70,
                "other": 0.69
            },
            "fee_unit": "per_kg"
        }
    }
}

UFH_AT_COMMERCIAL = {
    "fee_unit": "per_piece",
    "currency": "EUR",
    "effective_from": "2026-01-01",
    "min_annual_fee": 160.0,
    "vat_rate": 0.20,
    "early_payment_discount": 0.03,
    "notes": "Annual minimum EUR 160 excl. VAT. 3% discount if paid within 14 days.",
    "fee_schedule": {
        "large_appliance": {
            "commercial": {
                "lte_6kg": 0.045,
                "6_to_30kg": 0.120,
                "gt_30kg": 0.450,
                "luminaires": 0.050
            }
        },
        "cooling": {
            "commercial": {
                "lte_45kg": 5.200,
                "gt_45kg": 8.100,
                "heat_pump_fixed_ac": 7.000
            }
        },
        "display_screen": {
            "commercial": {
                "lte_10kg": 1.490,
                "10_to_25kg": 4.580,
                "gt_25kg": 7.210
            }
        },
        "small_appliance": {
            "commercial": {
                "lte_0_1kg": 0.010,
                "0_1_to_0_5kg": 0.020,
                "0_5_to_3kg": 0.050,
                "gt_3kg": 0.200,
                "luminaires": 0.050
            }
        },
        "small_it_telecom": {
            "commercial": {
                "lte_0_1kg": 0.010,
                "0_1_to_0_5kg": 0.020,
                "0_5_to_3kg": 0.050,
                "gt_3kg": 0.200
            }
        },
        "lamp": {
            "commercial": {
                "lte_0_04kg": 0.060,
                "gt_0_04kg": 0.130
            }
        },
        "photovoltaic": {
            "commercial": {"per_piece": 0.380},
            "fee_unit": "per_piece"
        },
        "industrial_battery": {
            "commercial": {
                "lithium_ion": 0.190,
                "lead_acid": 0.008,
                "other": 0.190,
                "system_light": 0.008
            },
            "fee_unit": "per_kg"
        },
        "ev_battery": {
            "commercial": {
                "lithium_ion": 0.045,
                "other": 0.045,
                "system_light": 0.008
            },
            "fee_unit": "per_kg"
        }
    }
}

# ---------------------------------------------------------------------------
# ECOASIMELEC Spain — WEEE (€/kg or €/unit by product code)
# Key rates for common product types
# ---------------------------------------------------------------------------
ECOASIMELEC_ES = {
    "fee_unit": "per_kg",
    "currency": "EUR",
    "effective_from": "2026-01-01",
    "min_quarterly_fee": 250.0,
    "joining_fee": 300.0,
    "notes": (
        "Joining fee EUR 300 (shared with ECOPILAS). Min quarterly fee EUR 250. "
        "Fees per product code per RD RAEE 110/2015. "
        "Household and professional rates may differ."
    ),
    "fee_schedule": {
        "cooling": {
            "household": {"per_kg": 0.195},
            "commercial": {"per_kg": 0.195}
        },
        "display_screen": {
            "household": {
                "led_tv_monitor": {"per_kg": 0.26},
                "laptop_tablet": {"per_kg": 0.11}
            },
            "commercial": {
                "led_tv_monitor": {"per_kg": 0.26},
                "laptop_tablet": {"per_kg": 0.11}
            }
        },
        "lamp": {
            "household": {
                "fluorescent_discharge": {"per_unit": 0.30},
                "compact_fluorescent": {"per_unit": 0.20},
                "led_lamp_tube": {"per_unit": 0.11}
            }
        },
        "large_appliance": {
            "household": {
                "washing_machine_dishwasher_dryer_oven": {"per_kg": 0.058},
                "electric_heater_water_heater": {"per_kg": 0.17},
                "microwave": {"per_kg": 0.058},
                "ventilation": {"per_kg": 0.04},
                "inverter_solar": {"per_kg": 0.04},
                "generator_transformer": {"per_kg": 0.048},
                "ebike": {"per_kg": 0.10},
                "inkjet_consumable": {"per_kg": 1.00},
                "toner_consumable": {"per_kg": 1.30}
            }
        },
        "small_appliance": {
            "household": {
                "general": {"per_kg": 0.10},
                "microwave": {"per_kg": 0.058},
                "medical": {"per_kg": 0.11},
                "power_strip_socket": {"per_kg": 0.09},
                "electricity_meter": {"per_kg": 0.025},
                "small_motor": {"per_kg": 0.048},
                "vape_ecigarette": {"per_kg": 0.12}
            }
        },
        "small_it_telecom": {
            "household": {
                "general": {"per_kg": 0.10},
                "mobile_phone": {"per_unit": 0.01},
                "inkjet_consumable": {"per_kg": 1.00},
                "toner_consumable": {"per_kg": 1.30}
            }
        },
        "photovoltaic": {
            "commercial": {
                "silicon": {"per_kg": 0.005},
                "other_non_hazardous": {"per_kg": 0.005},
                "hazardous_cdte": {"per_kg": 0.03}
            }
        },
        "luminaire_integrated_led": {
            "household": {
                "lte_1kg": {"per_unit": 0.07},
                "1_to_5kg": {"per_unit": 0.30},
                "gt_5kg": {"per_unit": 0.60}
            }
        }
    }
}

# ---------------------------------------------------------------------------
# Stichting OPEN Netherlands — WEEE (€/kg or €/piece)
# ---------------------------------------------------------------------------
STICHTING_OPEN_NL_WEEE = {
    "fee_unit": "mixed",
    "currency": "EUR",
    "effective_from": "2026-01-01",
    "notes": "Mandatory and only registry for WEEE in Netherlands. Fees excl. VAT.",
    "fee_schedule": {
        "cooling": {
            "household": {
                "fridge_freezer": {"per_kg": 0.420},
                "tumble_dryer_heat_pump": {"per_piece": 11.610},
                "ac_separate": {"per_piece": 9.670},
                "ac_builtin_heat_pump": {"per_kg": 0.010},
                "vending_machine_refrigerated": {"per_kg": 1.000}
            },
            "commercial": {
                "fridge_freezer": {"per_kg": 0.140}
            }
        },
        "display_screen": {
            "household": {
                "tv_flatscreen": {"per_kg": 0.580},
                "monitor_flatscreen": {"per_kg": 0.260},
                "laptop": {"per_kg": 0.096},
                "tablet_navigation": {"per_kg": 0.096}
            }
        },
        "lamp": {
            "household": {
                "led_lamp_tube": {"per_piece": 0.070},
                "energy_saving_discharge": {"per_piece": 0.140},
                "fluorescent": {"per_piece": 0.140}
            }
        },
        "large_appliance": {
            "household": {
                "washing_machine": {"per_piece": 17.520},
                "dishwasher": {"per_piece": 8.210},
                "tumble_dryer_no_heat_pump": {"per_piece": 11.610},
                "stove": {"per_piece": 7.290},
                "microwave_oven": {"per_piece": 2.500},
                "extractor_hood": {"per_piece": 2.400},
                "bbq_grill_cooking_plate": {"per_piece": 0.800},
                "household_kitchen_personal_care": {"per_piece": 0.330},
                "vacuum_floor_cleaner": {"per_piece": 0.370},
                "central_heating_boiler": {"per_kg": 0.120},
                "electric_tool": {"per_kg": 0.170},
                "audio_video": {"per_kg": 0.630},
                "it_office_household": {"per_kg": 0.096},
                "it_office_professional": {"per_kg": 0.025},
                "solar_panel": {"per_kg": 0.065},
                "ebike": {"per_kg": 0.040},
                "medical": {"per_kg": 0.250},
                "measuring_control": {"per_kg": 0.020},
                "sunbed": {"per_piece": 30.400}
            }
        },
        "small_appliance": {
            "household": {
                "microwave_oven": {"per_piece": 4.450},
                "vacuum_floor_cleaner": {"per_piece": 2.430},
                "household_kitchen_personal_care": {"per_piece": 0.140},
                "bbq_grill_cooking_plate": {"per_piece": 0.500},
                "audio_video": {"per_kg": 0.630},
                "electric_tool": {"per_kg": 0.170},
                "medical": {"per_kg": 0.160},
                "measuring_control": {"per_kg": 0.080},
                "game_computer": {"per_kg": 0.060},
                "toys_leisure_sports": {"per_kg": 0.120}
            }
        },
        "small_it_telecom": {
            "household": {
                "mobile_phone": {"per_kg": 0.096},
                "desktop_computer": {"per_kg": 0.096},
                "printer_scanner": {"per_kg": 0.096},
                "ict_office_household": {"per_kg": 0.096},
                "ict_office_professional": {"per_kg": 0.025}
            }
        },
        "luminaire": {
            "household": {
                "gt_750g": {"per_piece": 0.210},
                "lte_750g": {"per_piece": 0.070}
            }
        }
    }
}

# ---------------------------------------------------------------------------
# Stichting OPEN Netherlands — Batteries (€/piece, weight + chemistry)
# ---------------------------------------------------------------------------
STICHTING_OPEN_NL_BATTERIES = {
    "fee_unit": "per_piece",
    "currency": "EUR",
    "effective_from": "2026-01-01",
    "notes": (
        "Mandatory and only registry for batteries in Netherlands. Fees excl. VAT. "
        "Battery pack: if no shock-resistant casing (visible cells in shrink tube), "
        "declare per cell (number x weight per cell), not as pack."
    ),
    "fee_schedule": {
        "portable_battery": {
            "by_weight_grams": {
                "lte_50g": {
                    "lithium_ion": 0.038,
                    "lithium_tcl": 0.306,
                    "lead_acid": 0.021,
                    "nimh": 0.016,
                    "other": 0.027
                },
                "51_to_150g": {
                    "lithium_ion": 0.184,
                    "lithium_tcl": 1.507,
                    "lead_acid": 0.111,
                    "nimh": 0.079,
                    "other": 0.143
                },
                "151_to_250g": {
                    "lithium_ion": 0.368,
                    "lithium_tcl": 2.999,
                    "lead_acid": 0.197,
                    "nimh": 0.141,
                    "other": 0.252
                },
                "251_to_500g": {
                    "lithium_ion": 0.661,
                    "lithium_tcl": 5.397,
                    "lead_acid": 0.249,
                    "nimh": 0.289,
                    "other": 0.523
                },
                "501_to_750g": {
                    "lithium_ion": 1.103,
                    "lithium_tcl": 9.010,
                    "lead_acid": 0.302,
                    "nimh": 0.394,
                    "other": 0.712
                },
                "751_to_1000g": {
                    "lithium_ion": 1.690,
                    "lithium_tcl": 13.810,
                    "lead_acid": 0.354,
                    "nimh": 0.560,
                    "other": 1.011
                },
                "gt_1000g": {
                    "lithium_ion": 4.356,
                    "lithium_tcl": 35.582,
                    "lead_acid": 0.406,
                    "nimh": 1.073,
                    "other": 1.943
                }
            },
            "button_cell": {
                "lithium_ion": 0.009,
                "lithium_tcl": 0.076,
                "lead_acid": 0.003,
                "nimh": 0.003,
                "other": 0.004
            }
        },
        "ebike_battery": {
            "lithium_ion": 1.268,
            "fee_unit": "per_kg",
            "notes": "Weight of entire e-bike battery pack."
        }
    }
}

PRO_FEE_UPDATES = [
    ("ufh-at-weee", {**UFH_AT_HOUSEHOLD, **{"commercial_schedule": UFH_AT_COMMERCIAL["fee_schedule"]}}),
    ("ufh-at-batteries", {**UFH_AT_HOUSEHOLD, **{"commercial_schedule": UFH_AT_COMMERCIAL["fee_schedule"]}}),
    ("ecoasimelec-es", ECOASIMELEC_ES),
    ("stichting-open-nl-weee", STICHTING_OPEN_NL_WEEE),
    ("stichting-open-nl-batteries", STICHTING_OPEN_NL_BATTERIES),
]


def upgrade() -> None:
    conn = op.get_bind()
    for pro_key, config in PRO_FEE_UPDATES:
        conn.execute(
            sa.text(
                "UPDATE pro_organisations "
                "SET report_template_config = :config, updated_at = now() "
                "WHERE pro_key = :pro_key"
            ),
            {"config": json.dumps(config), "pro_key": pro_key},
        )


def downgrade() -> None:
    conn = op.get_bind()
    keys = [p[0] for p in PRO_FEE_UPDATES]
    conn.execute(
        sa.text(
            "UPDATE pro_organisations "
            "SET report_template_config = NULL, updated_at = now() "
            "WHERE pro_key = ANY(:keys)"
        ),
        {"keys": keys},
    )
