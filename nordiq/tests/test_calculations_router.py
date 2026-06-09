"""Unit tests for calculations router helpers (no DB, no HTTP server needed).

We test the pure-logic parts: _resolve_period in the frontend page, and that the
calculator + rate-set wiring produces the correct obligation shape that the router
would persist.  Full integration tests require a running Postgres and are out of scope
for the unit suite.
"""

from datetime import date
from decimal import Decimal

import pytest

from nordiq.calculators.base import ReportingPeriod
from nordiq.calculators.nordic.packaging import NordicPackagingCalculator, RateSet
from nordiq.calculators.registry import get_calculator_class
from nordiq.ingestion.base import NormalizedProductData
from nordiq.models.enums import DataRecordSource, MaterialType, ProductCategory

# ---------------------------------------------------------------------------
# Helpers mirrored from the router (no DB call)
# ---------------------------------------------------------------------------

RATE_SET = RateSet(
    country_code="FI",
    product_category=ProductCategory.PACKAGING,
    currency="EUR",
    rates={
        "plastic": Decimal("0.45"),
        "paper": Decimal("0.08"),
        "glass": Decimal("0.06"),
        "metal": Decimal("0.12"),
        "wood": Decimal("0.04"),
        "other": Decimal("0.20"),
    },
    valid_from=date(2024, 1, 1),
)

PERIOD = ReportingPeriod(start=date(2024, 1, 1), end=date(2024, 12, 31))


def _make_product(material: str, weight_kg: float) -> NormalizedProductData:
    return NormalizedProductData(
        external_product_id="SKU-1",
        description="Test",
        product_category=ProductCategory.PACKAGING,
        weight_kg=weight_kg,
        material_type=MaterialType(material),
        reporting_period_start=date(2024, 1, 1),
        reporting_period_end=date(2024, 12, 31),
        source=DataRecordSource.CSV,
        raw_record={},
    )


# ---------------------------------------------------------------------------
# Registry wiring
# ---------------------------------------------------------------------------

def test_registry_returns_nordic_calculator_for_fi():
    cls = get_calculator_class("FI", ProductCategory.PACKAGING)
    assert cls is NordicPackagingCalculator


@pytest.mark.parametrize("country", ["FI", "SE", "NO", "DK"])
def test_registry_all_nordic_countries(country):
    cls = get_calculator_class(country, ProductCategory.PACKAGING)
    assert cls is NordicPackagingCalculator


# ---------------------------------------------------------------------------
# Calculation correctness (mirrors what router does)
# ---------------------------------------------------------------------------

def test_single_plastic_product():
    calc = NordicPackagingCalculator(RATE_SET)
    products = [_make_product("plastic", 10.0)]
    ob = calc.calculate(products, PERIOD)

    assert ob.country_code == "FI"
    assert ob.currency == "EUR"
    assert ob.total_weight_kg == Decimal("10")
    assert ob.fee_amount == Decimal("4.5000")  # 10 * 0.45


def test_mixed_materials_fee():
    calc = NordicPackagingCalculator(RATE_SET)
    products = [
        _make_product("plastic", 10.0),   # 10 * 0.45 = 4.5000
        _make_product("paper", 5.0),      #  5 * 0.08 = 0.4000
        _make_product("glass", 2.0),      #  2 * 0.06 = 0.1200
    ]
    ob = calc.calculate(products, PERIOD)
    assert ob.fee_amount == Decimal("5.0200")
    assert ob.total_weight_kg == Decimal("17")


def test_zero_products_returns_zero_fee():
    calc = NordicPackagingCalculator(RATE_SET)
    ob = calc.calculate([], PERIOD)
    assert ob.fee_amount == Decimal("0")
    assert ob.total_weight_kg == Decimal("0")


def test_out_of_period_products_excluded():
    calc = NordicPackagingCalculator(RATE_SET)
    product = NormalizedProductData(
        external_product_id="SKU-OLD",
        description="Old",
        product_category=ProductCategory.PACKAGING,
        weight_kg=100.0,
        material_type=MaterialType.PLASTIC,
        reporting_period_start=date(2022, 1, 1),
        reporting_period_end=date(2022, 12, 31),
        source=DataRecordSource.CSV,
        raw_record={},
    )
    ob = calc.calculate([product], PERIOD)
    assert ob.fee_amount == Decimal("0")
    assert ob.calculation_snapshot["products_in_scope"] == 0


def test_calculation_snapshot_contains_all_keys():
    calc = NordicPackagingCalculator(RATE_SET)
    ob = calc.calculate([_make_product("plastic", 1.0)], PERIOD)
    snap = ob.calculation_snapshot
    for key in (
        "calculator", "country_code", "product_category",
        "reporting_period", "rate_set", "rates_used",
        "weight_by_material_kg", "fee_by_material",
        "total_weight_kg", "total_fee", "currency",
        "products_in_scope", "products_total",
    ):
        assert key in snap, f"Missing key in snapshot: {key}"


def test_snapshot_values_are_strings_for_json_safety():
    """Ensure Decimal values are stored as strings (JSON-serialisable)."""
    calc = NordicPackagingCalculator(RATE_SET)
    ob = calc.calculate([_make_product("plastic", 5.0)], PERIOD)
    snap = ob.calculation_snapshot
    for val in snap["rates_used"].values():
        assert isinstance(val, str)
    for val in snap["weight_by_material_kg"].values():
        assert isinstance(val, str)
    for val in snap["fee_by_material"].values():
        assert isinstance(val, str)
    assert isinstance(snap["total_fee"], str)
    assert isinstance(snap["total_weight_kg"], str)


def test_pro_id_format():
    calc = NordicPackagingCalculator(RATE_SET)
    ob = calc.calculate([], PERIOD)
    assert ob.pro_id == "nordic_pro_fi"


def test_other_material_fallback_rate():
    rate_set = RateSet(
        country_code="FI",
        product_category=ProductCategory.PACKAGING,
        currency="EUR",
        rates={"other": Decimal("0.20")},
        valid_from=date(2024, 1, 1),
    )
    calc = NordicPackagingCalculator(rate_set)
    ob = calc.calculate([_make_product("plastic", 10.0)], PERIOD)
    # "plastic" not in rates → falls back to "other" = 0.20
    assert ob.fee_amount == Decimal("2.0000")


def test_missing_rate_raises():
    rate_set = RateSet(
        country_code="FI",
        product_category=ProductCategory.PACKAGING,
        currency="EUR",
        rates={"paper": Decimal("0.08")},  # no "plastic" and no "other"
        valid_from=date(2024, 1, 1),
    )
    calc = NordicPackagingCalculator(rate_set)
    with pytest.raises(ValueError, match="No EPR rate for material"):
        calc.calculate([_make_product("plastic", 10.0)], PERIOD)


# ---------------------------------------------------------------------------
# Period overlap boundary cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("p_start,p_end,expected_in_scope", [
    # exactly matching period
    (date(2024, 1, 1), date(2024, 12, 31), 1),
    # product period ends on period start (touching boundary — in scope)
    (date(2023, 6, 1), date(2024, 1, 1), 1),
    # product period starts on period end (touching — in scope)
    (date(2024, 12, 31), date(2025, 3, 31), 1),
    # fully before period
    (date(2022, 1, 1), date(2023, 12, 31), 0),
    # fully after period
    (date(2025, 1, 1), date(2025, 12, 31), 0),
])
def test_period_overlap(p_start, p_end, expected_in_scope):
    calc = NordicPackagingCalculator(RATE_SET)
    product = NormalizedProductData(
        external_product_id="SKU-X",
        description="X",
        product_category=ProductCategory.PACKAGING,
        weight_kg=1.0,
        material_type=MaterialType.PLASTIC,
        reporting_period_start=p_start,
        reporting_period_end=p_end,
        source=DataRecordSource.CSV,
        raw_record={},
    )
    ob = calc.calculate([product], PERIOD)
    assert ob.calculation_snapshot["products_in_scope"] == expected_in_scope
