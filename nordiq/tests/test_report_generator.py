"""Unit tests for NordicReportGenerator — file output, CSV structure, manifest content."""

import csv
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from nordiq.calculators.base import EPRObligation, ReportingPeriod
from nordiq.calculators.nordic.packaging import NordicPackagingCalculator, RateEntry, RateSet
from nordiq.models.enums import DataRecordSource, MaterialType, ProductCategory
from nordiq.ingestion.base import NormalizedProductData
from nordiq.pro_connectors.nordic.report_generator import NordicReportGenerator, _sha256

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PERIOD_2024 = ReportingPeriod(start=date(2024, 1, 1), end=date(2024, 12, 31))

FI_RATES = RateSet(
    country_code="FI",
    product_category=ProductCategory.PACKAGING,
    currency="EUR",
    rates={
        "plastic": RateEntry(rate_per_kg=Decimal("0.45")),
        "paper":   RateEntry(rate_per_kg=Decimal("0.08")),
        "glass":   RateEntry(rate_per_kg=Decimal("0.06")),
        "metal":   RateEntry(rate_per_kg=Decimal("0.12")),
        "wood":    RateEntry(rate_per_kg=Decimal("0.04")),
        "other":   RateEntry(rate_per_kg=Decimal("0.20")),
    },
    valid_from=date(2024, 1, 1),
    regulation_reference="FI Packaging Producers Ltd 2024 fee schedule",
)


def _product(material: MaterialType, weight_kg: str):
    return NormalizedProductData(
        external_product_id="SKU-001",
        description="Test product",
        product_category=ProductCategory.PACKAGING,
        weight_kg=Decimal(weight_kg),
        material_type=material,
        reporting_period_start=date(2024, 1, 1),
        reporting_period_end=date(2024, 12, 31),
        source=DataRecordSource.CSV,
        raw_record={},
    )


def _make_obligation(products=None) -> EPRObligation:
    if products is None:
        products = [
            _product(MaterialType.PLASTIC, "10.0"),
            _product(MaterialType.PAPER, "20.0"),
        ]
    calc = NordicPackagingCalculator(FI_RATES)
    return calc.calculate(products, PERIOD_2024)


# ---------------------------------------------------------------------------
# ReportFile descriptor
# ---------------------------------------------------------------------------

def test_generate_returns_report_file(tmp_path):
    gen = NordicReportGenerator(tmp_path)
    report = gen.generate(_make_obligation())
    assert report.file_format == "csv"
    assert Path(report.file_path).exists()
    assert report.checksum  # non-empty SHA-256


def test_obligation_id_in_report_file(tmp_path):
    gen = NordicReportGenerator(tmp_path)
    report = gen.generate(_make_obligation())
    assert "FI" in report.obligation_id
    assert "packaging" in report.obligation_id
    assert "2024-01-01" in report.obligation_id


def test_csv_filename_contains_key_info(tmp_path):
    gen = NordicReportGenerator(tmp_path)
    report = gen.generate(_make_obligation())
    name = Path(report.file_path).name
    assert "FI" in name
    assert "packaging" in name
    assert "2024-01-01" in name
    assert name.endswith(".csv")


def test_output_dir_created_automatically(tmp_path):
    nested = tmp_path / "reports" / "2024"
    gen = NordicReportGenerator(nested)
    gen.generate(_make_obligation())
    assert nested.exists()


# ---------------------------------------------------------------------------
# CSV content
# ---------------------------------------------------------------------------

def _read_csv(report_file) -> list[dict]:
    with open(report_file.file_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_csv_has_required_columns(tmp_path):
    gen = NordicReportGenerator(tmp_path)
    report = gen.generate(_make_obligation())
    rows = _read_csv(report)
    required = {
        "country_code", "pro_id", "product_category",
        "reporting_period_start", "reporting_period_end",
        "material_type", "weight_kg", "rate_per_kg", "fee_amount", "currency",
    }
    assert required == set(rows[0].keys())


def test_csv_has_one_row_per_material_plus_total(tmp_path):
    products = [
        _product(MaterialType.PLASTIC, "10.0"),
        _product(MaterialType.PAPER, "20.0"),
        _product(MaterialType.GLASS, "5.0"),
    ]
    gen = NordicReportGenerator(tmp_path)
    report = gen.generate(_make_obligation(products))
    rows = _read_csv(report)
    material_rows = [r for r in rows if r["material_type"] != "TOTAL"]
    total_rows = [r for r in rows if r["material_type"] == "TOTAL"]
    assert len(material_rows) == 3
    assert len(total_rows) == 1


def test_csv_total_row_has_correct_fee(tmp_path):
    # 10 kg plastic × 0.45 + 20 kg paper × 0.08 = 4.50 + 1.60 = 6.10
    gen = NordicReportGenerator(tmp_path)
    report = gen.generate(_make_obligation())
    rows = _read_csv(report)
    total = next(r for r in rows if r["material_type"] == "TOTAL")
    assert Decimal(total["fee_amount"]) == Decimal("6.1000")
    assert Decimal(total["weight_kg"]) == Decimal("30.0")


def test_csv_material_rows_have_correct_weights(tmp_path):
    gen = NordicReportGenerator(tmp_path)
    report = gen.generate(_make_obligation())
    rows = _read_csv(report)
    by_material = {r["material_type"]: r for r in rows if r["material_type"] != "TOTAL"}
    assert Decimal(by_material["plastic"]["weight_kg"]) == Decimal("10.0")
    assert Decimal(by_material["paper"]["weight_kg"]) == Decimal("20.0")


def test_csv_material_rows_have_correct_rates(tmp_path):
    gen = NordicReportGenerator(tmp_path)
    report = gen.generate(_make_obligation())
    rows = _read_csv(report)
    by_material = {r["material_type"]: r for r in rows if r["material_type"] != "TOTAL"}
    assert Decimal(by_material["plastic"]["rate_per_kg"]) == Decimal("0.45")
    assert Decimal(by_material["paper"]["rate_per_kg"]) == Decimal("0.08")


def test_csv_country_and_currency_correct(tmp_path):
    gen = NordicReportGenerator(tmp_path)
    report = gen.generate(_make_obligation())
    rows = _read_csv(report)
    assert all(r["country_code"] == "FI" for r in rows)
    assert all(r["currency"] == "EUR" for r in rows)


def test_csv_reporting_period_correct(tmp_path):
    gen = NordicReportGenerator(tmp_path)
    report = gen.generate(_make_obligation())
    rows = _read_csv(report)
    assert all(r["reporting_period_start"] == "2024-01-01" for r in rows)
    assert all(r["reporting_period_end"] == "2024-12-31" for r in rows)


# ---------------------------------------------------------------------------
# Manifest JSON
# ---------------------------------------------------------------------------

def _read_manifest(report_file) -> dict:
    manifest_path = Path(report_file.file_path).with_name(
        Path(report_file.file_path).stem + "_manifest.json"
    )
    with open(manifest_path, encoding="utf-8") as f:
        return json.load(f)


def test_manifest_file_exists(tmp_path):
    gen = NordicReportGenerator(tmp_path)
    report = gen.generate(_make_obligation())
    manifest_path = Path(report.file_path).parent / (
        Path(report.file_path).stem + "_manifest.json"
    )
    assert manifest_path.exists()


def test_manifest_contains_calculation_snapshot(tmp_path):
    gen = NordicReportGenerator(tmp_path)
    report = gen.generate(_make_obligation())
    manifest = _read_manifest(report)
    assert "calculation_snapshot" in manifest
    snap = manifest["calculation_snapshot"]
    assert snap["country_code"] == "FI"
    assert snap["calculator"] == "NordicPackagingCalculator"


def test_manifest_totals_match_csv(tmp_path):
    gen = NordicReportGenerator(tmp_path)
    obligation = _make_obligation()
    report = gen.generate(obligation)
    manifest = _read_manifest(report)
    assert Decimal(manifest["total_fee"]) == obligation.fee_amount
    assert Decimal(manifest["total_weight_kg"]) == obligation.total_weight_kg


def test_manifest_has_generated_at_timestamp(tmp_path):
    gen = NordicReportGenerator(tmp_path)
    report = gen.generate(_make_obligation())
    manifest = _read_manifest(report)
    assert "generated_at" in manifest
    assert "T" in manifest["generated_at"]  # ISO 8601 format


# ---------------------------------------------------------------------------
# Checksum
# ---------------------------------------------------------------------------

def test_checksum_is_sha256_hex(tmp_path):
    gen = NordicReportGenerator(tmp_path)
    report = gen.generate(_make_obligation())
    assert len(report.checksum) == 64
    assert all(c in "0123456789abcdef" for c in report.checksum)


def test_checksum_matches_file_content(tmp_path):
    gen = NordicReportGenerator(tmp_path)
    report = gen.generate(_make_obligation())
    assert report.checksum == _sha256(Path(report.file_path))


def test_different_obligations_different_checksums(tmp_path):
    products_a = [_product(MaterialType.PLASTIC, "10.0")]
    products_b = [_product(MaterialType.PLASTIC, "99.0")]
    gen = NordicReportGenerator(tmp_path)
    report_a = gen.generate(_make_obligation(products_a))
    report_b = gen.generate(_make_obligation(products_b))
    assert report_a.checksum != report_b.checksum


# ---------------------------------------------------------------------------
# Empty obligation (zero weight)
# ---------------------------------------------------------------------------

def test_empty_obligation_generates_valid_csv(tmp_path):
    calc = NordicPackagingCalculator(FI_RATES)
    obligation = calc.calculate([], PERIOD_2024)
    gen = NordicReportGenerator(tmp_path)
    report = gen.generate(obligation)
    rows = _read_csv(report)
    # Only the TOTAL row (no material rows)
    assert len(rows) == 1
    assert rows[0]["material_type"] == "TOTAL"
    assert Decimal(rows[0]["fee_amount"]) == Decimal("0")
