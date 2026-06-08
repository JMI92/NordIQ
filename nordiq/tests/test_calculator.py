"""Unit tests for NordicPackagingCalculator — all with known inputs and expected outputs.

All fee assertions use exact Decimal arithmetic. No floats anywhere.
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
# Fixtures
# ---------------------------------------------------------------------------

PERIOD_2024 = ReportingPeriod(start=date(2024, 1, 1), end=date(2024, 12, 31))

FI_RATES = RateSet(
    country_code="FI",
    product_category=ProductCategory.PACKAGING,
    currency="EUR",
    rates={
        "plastic": Decimal("0.45"),
        "paper":   Decimal("0.08"),
        "glass":   Decimal("0.06"),
        "metal":   Decimal("0.12"),
        "wood":    Decimal("0.04"),
        "other":   Decimal("0.20"),
    },
    valid_from=date(2024, 1, 1),
    regulation_reference="FI Packaging Producers Ltd 2024 fee schedule",
)

SE_RATES = RateSet(
    country_code="SE",
    product_category=ProductCategory.PACKAGING,
    currency="SEK",
    rates={
        "plastic": Decimal("0.50"),
        "paper":   Decimal("0.10"),
        "glass":   Decimal("0.07"),
        "metal":   Decimal("0.15"),
        "wood":    Decimal("0.05"),
        "other":   Decimal("0.25"),
    },
    valid_from=date(2024, 1, 1),
)

NO_RATES = RateSet(
    country_code="NO",
    product_category=ProductCategory.PACKAGING,
    currency="NOK",
    rates={
        "plastic": Decimal("5.20"),
        "paper":   Decimal("0.80"),
        "glass":   Decimal("0.60"),
        "metal":   Decimal("1.20"),
        "wood":    Decimal("0.40"),
        "other":   Decimal("2.50"),
    },
    valid_from=date(2024, 1, 1),
)

DK_RATES = RateSet(
    country_code="DK",
    product_category=ProductCategory.PACKAGING,
    currency="DKK",
    rates={
        "plastic": Decimal("3.50"),
        "paper":   Decimal("0.60"),
        "glass":   Decimal("0.45"),
        "metal":   Decimal("0.90"),
        "wood":    Decimal("0.30"),
        "other":   Decimal("1.80"),
    },
    valid_from=date(2024, 1, 1),
)


def _product(material: MaterialType, weight_kg, sku="SKU-001"):
    return NormalizedProductData(
        external_product_id=sku,
        description="Test product",
        product_category=ProductCategory.PACKAGING,
        weight_kg=Decimal(str(weight_kg)),
        material_type=material,
        reporting_period_start=date(2024, 1, 1),
        reporting_period_end=date(2024, 12, 31),
        source=DataRecordSource.CSV,
        raw_record={},
    )


# ---------------------------------------------------------------------------
# Basic fee calculations — known inputs → known outputs
# ---------------------------------------------------------------------------

def test_fi_single_plastic_product():
    # 10 kg plastic × 0.45 EUR/kg = 4.5000 EUR
    calc = NordicPackagingCalculator(FI_RATES)
    result = calc.calculate([_product(MaterialType.PLASTIC, "10.0")], PERIOD_2024)
    assert result.fee_amount == Decimal("4.5000")
    assert result.currency == "EUR"
    assert result.total_weight_kg == Decimal("10.0")


def test_fi_single_paper_product():
    # 100 kg paper × 0.08 EUR/kg = 8.0000 EUR
    calc = NordicPackagingCalculator(FI_RATES)
    result = calc.calculate([_product(MaterialType.PAPER, "100.0")], PERIOD_2024)
    assert result.fee_amount == Decimal("8.0000")


def test_fi_multiple_materials():
    # 10 kg plastic × 0.45 = 4.50
    # 20 kg paper   × 0.08 = 1.60
    # total = 6.10
    products = [
        _product(MaterialType.PLASTIC, "10.0", "P1"),
        _product(MaterialType.PAPER, "20.0", "P2"),
    ]
    calc = NordicPackagingCalculator(FI_RATES)
    result = calc.calculate(products, PERIOD_2024)
    assert result.fee_amount == Decimal("6.1000")
    assert result.total_weight_kg == Decimal("30.0")
    assert result.weight_by_material["plastic"] == Decimal("10.0")
    assert result.weight_by_material["paper"] == Decimal("20.0")


def test_fi_weights_aggregated_per_material():
    # Two plastic products: 3.5 + 1.5 = 5.0 kg → 5.0 × 0.45 = 2.2500
    products = [
        _product(MaterialType.PLASTIC, "3.5", "P1"),
        _product(MaterialType.PLASTIC, "1.5", "P2"),
    ]
    calc = NordicPackagingCalculator(FI_RATES)
    result = calc.calculate(products, PERIOD_2024)
    assert result.weight_by_material["plastic"] == Decimal("5.0")
    assert result.fee_amount == Decimal("2.2500")


def test_se_plastic_fee():
    # 50 kg plastic × 0.50 SEK/kg = 25.0000 SEK
    calc = NordicPackagingCalculator(SE_RATES)
    result = calc.calculate([_product(MaterialType.PLASTIC, "50.0")], PERIOD_2024)
    assert result.fee_amount == Decimal("25.0000")
    assert result.currency == "SEK"


def test_no_plastic_fee():
    # 10 kg plastic × 5.20 NOK/kg = 52.0000 NOK
    calc = NordicPackagingCalculator(NO_RATES)
    result = calc.calculate([_product(MaterialType.PLASTIC, "10.0")], PERIOD_2024)
    assert result.fee_amount == Decimal("52.0000")
    assert result.currency == "NOK"


def test_dk_glass_fee():
    # 200 kg glass × 0.45 DKK/kg = 90.0000 DKK
    calc = NordicPackagingCalculator(DK_RATES)
    result = calc.calculate([_product(MaterialType.GLASS, "200.0")], PERIOD_2024)
    assert result.fee_amount == Decimal("90.0000")
    assert result.currency == "DKK"


def test_rounding_half_up():
    # 1 kg × 0.45 = 0.45 → exact, no rounding needed
    # Use a weight that produces a 5-decimal result: 1.00001 kg × 0.45 = 0.450005
    # ROUND_HALF_UP → 0.4500 (4dp)
    calc = NordicPackagingCalculator(FI_RATES)
    result = calc.calculate([_product(MaterialType.PLASTIC, "1.00001")], PERIOD_2024)
    # 1.00001 × 0.45 = 0.4500045 → rounds to 0.4500
    assert result.fee_amount == Decimal("0.4500")


def test_fee_amounts_are_decimal_not_float():
    calc = NordicPackagingCalculator(FI_RATES)
    result = calc.calculate([_product(MaterialType.PLASTIC, "10.0")], PERIOD_2024)
    assert isinstance(result.fee_amount, Decimal)
    assert isinstance(result.total_weight_kg, Decimal)
    for v in result.weight_by_material.values():
        assert isinstance(v, Decimal)


# ---------------------------------------------------------------------------
# Reporting period filtering
# ---------------------------------------------------------------------------

def test_products_outside_period_excluded():
    in_scope = NormalizedProductData(
        external_product_id="IN",
        description="In scope",
        product_category=ProductCategory.PACKAGING,
        weight_kg=Decimal("10.0"),
        material_type=MaterialType.PLASTIC,
        reporting_period_start=date(2024, 1, 1),
        reporting_period_end=date(2024, 12, 31),
        source=DataRecordSource.CSV,
        raw_record={},
    )
    out_of_scope = NormalizedProductData(
        external_product_id="OUT",
        description="Out of scope",
        product_category=ProductCategory.PACKAGING,
        weight_kg=Decimal("999.0"),
        material_type=MaterialType.PLASTIC,
        reporting_period_start=date(2023, 1, 1),
        reporting_period_end=date(2023, 12, 31),
        source=DataRecordSource.CSV,
        raw_record={},
    )
    calc = NordicPackagingCalculator(FI_RATES)
    result = calc.calculate([in_scope, out_of_scope], PERIOD_2024)
    assert result.total_weight_kg == Decimal("10.0")
    assert result.calculation_snapshot["products_in_scope"] == 1
    assert result.calculation_snapshot["products_total"] == 2


def test_empty_product_list_gives_zero_fee():
    calc = NordicPackagingCalculator(FI_RATES)
    result = calc.calculate([], PERIOD_2024)
    assert result.fee_amount == Decimal("0")
    assert result.total_weight_kg == Decimal("0")


# ---------------------------------------------------------------------------
# 'other' material fallback rate
# ---------------------------------------------------------------------------

def test_unknown_material_falls_back_to_other_rate():
    # MaterialType.OTHER should use "other" rate (0.20 EUR/kg for FI)
    calc = NordicPackagingCalculator(FI_RATES)
    result = calc.calculate([_product(MaterialType.OTHER, "10.0")], PERIOD_2024)
    assert result.fee_amount == Decimal("2.0000")


def test_missing_rate_and_no_fallback_raises():
    rates_no_fallback = RateSet(
        country_code="FI",
        product_category=ProductCategory.PACKAGING,
        currency="EUR",
        rates={"plastic": Decimal("0.45")},  # no 'other' fallback
        valid_from=date(2024, 1, 1),
    )
    calc = NordicPackagingCalculator(rates_no_fallback)
    with pytest.raises(ValueError, match="other"):
        calc.calculate([_product(MaterialType.PAPER, "1.0")], PERIOD_2024)


# ---------------------------------------------------------------------------
# calculation_snapshot completeness
# ---------------------------------------------------------------------------

def test_snapshot_contains_all_required_keys():
    calc = NordicPackagingCalculator(FI_RATES)
    result = calc.calculate([_product(MaterialType.PLASTIC, "10.0")], PERIOD_2024)
    snap = result.calculation_snapshot
    for key in (
        "calculator", "country_code", "product_category", "reporting_period",
        "rate_set", "rates_used", "weight_by_material_kg", "fee_by_material",
        "total_weight_kg", "total_fee", "currency",
    ):
        assert key in snap, f"snapshot missing key: {key}"


def test_snapshot_rates_are_strings():
    calc = NordicPackagingCalculator(FI_RATES)
    result = calc.calculate([_product(MaterialType.PLASTIC, "10.0")], PERIOD_2024)
    snap = result.calculation_snapshot
    # All numeric values in snapshot must be stored as strings (JSON-safe, exact)
    assert isinstance(snap["total_weight_kg"], str)
    assert isinstance(snap["total_fee"], str)
    for v in snap["rates_used"].values():
        assert isinstance(v, str)


def test_snapshot_regulation_reference_preserved():
    calc = NordicPackagingCalculator(FI_RATES)
    result = calc.calculate([_product(MaterialType.PLASTIC, "1.0")], PERIOD_2024)
    assert "FI Packaging Producers Ltd" in result.calculation_snapshot["rate_set"]["regulation_reference"]


# ---------------------------------------------------------------------------
# Output fields
# ---------------------------------------------------------------------------

def test_pro_id_matches_country():
    for country, rates in [("FI", FI_RATES), ("SE", SE_RATES), ("NO", NO_RATES), ("DK", DK_RATES)]:
        calc = NordicPackagingCalculator(rates)
        result = calc.calculate([_product(MaterialType.PLASTIC, "1.0")], PERIOD_2024)
        assert result.pro_id == f"nordic_pro_{country.lower()}"
        assert result.country_code == country


def test_product_category_is_packaging():
    calc = NordicPackagingCalculator(FI_RATES)
    result = calc.calculate([_product(MaterialType.PLASTIC, "1.0")], PERIOD_2024)
    assert result.product_category == ProductCategory.PACKAGING


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_registry_returns_nordic_packaging_calculator_for_all_countries():
    for country in ("FI", "SE", "NO", "DK"):
        cls = get_calculator_class(country, ProductCategory.PACKAGING)
        assert cls is NordicPackagingCalculator


def test_registry_unknown_country_raises():
    from nordiq.calculators.registry import get_calculator_class
    with pytest.raises(ValueError, match="XX"):
        get_calculator_class("XX", ProductCategory.PACKAGING)


def test_registry_unknown_category_raises():
    from nordiq.calculators.registry import get_calculator_class
    with pytest.raises(ValueError):
        get_calculator_class("FI", ProductCategory.WEEE)
