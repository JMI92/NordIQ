"""Unit tests for the PRO submission connector and report generation pipeline."""

from __future__ import annotations

import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from nordiq.calculators.base import EPRObligation, ReportingPeriod
from nordiq.models.enums import ProductCategory
from nordiq.pro_connectors.base import ReportFile, SubmissionResult
from nordiq.pro_connectors.nordic.connector import NordicPROConnector
from nordiq.pro_connectors.nordic.report_generator import NordicReportGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PERIOD = ReportingPeriod(start=date(2024, 1, 1), end=date(2024, 12, 31))


def _make_obligation(
    country: str = "FI",
    weight_by_material: dict | None = None,
    fee_amount: str = "5.0000",
) -> EPRObligation:
    wbm = {"plastic": Decimal("10"), "paper": Decimal("5")} if weight_by_material is None else weight_by_material
    return EPRObligation(
        country_code=country,
        pro_id=f"nordic_pro_{country.lower()}",
        product_category=ProductCategory.PACKAGING,
        reporting_period=PERIOD,
        total_weight_kg=sum(wbm.values(), Decimal(0)),
        fee_amount=Decimal(fee_amount),
        currency="EUR",
        weight_by_material=wbm,
        calculation_snapshot={
            "rates_used": {"plastic": "0.45", "paper": "0.08"},
            "weight_by_material_kg": {m: str(w) for m, w in wbm.items()},
            "fee_by_material": {"plastic": "4.5000", "paper": "0.4000"},
            "total_fee": fee_amount,
            "total_weight_kg": str(sum(wbm.values(), Decimal(0))),
            "currency": "EUR",
            "rate_set": {"regulation_reference": "FI 2024"},
        },
    )


# ---------------------------------------------------------------------------
# NordicReportGenerator
# ---------------------------------------------------------------------------

class TestNordicReportGenerator:
    def test_generate_creates_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = NordicReportGenerator(tmpdir)
            ob = _make_obligation()
            rf = gen.generate(ob)
            assert Path(rf.file_path).exists()
            assert rf.file_format == "csv"

    def test_generate_creates_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = NordicReportGenerator(tmpdir)
            ob = _make_obligation()
            gen.generate(ob)
            manifests = list(Path(tmpdir).glob("*_manifest.json"))
            assert len(manifests) == 1

    def test_csv_has_total_row(self):
        import csv as csv_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            gen = NordicReportGenerator(tmpdir)
            ob = _make_obligation()
            rf = gen.generate(ob)
            with open(rf.file_path) as f:
                rows = list(csv_mod.DictReader(f))
            material_types = [r["material_type"] for r in rows]
            assert "TOTAL" in material_types

    def test_csv_material_rows_match_weight_by_material(self):
        import csv as csv_mod

        wbm = {"plastic": Decimal("10"), "glass": Decimal("3")}
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = NordicReportGenerator(tmpdir)
            ob = _make_obligation(weight_by_material=wbm)
            rf = gen.generate(ob)
            with open(rf.file_path) as f:
                rows = list(csv_mod.DictReader(f))
            non_total = [r for r in rows if r["material_type"] != "TOTAL"]
            assert len(non_total) == 2
            materials = {r["material_type"] for r in non_total}
            assert materials == {"plastic", "glass"}

    def test_checksum_is_sha256_hex(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = NordicReportGenerator(tmpdir)
            ob = _make_obligation()
            rf = gen.generate(ob)
            assert len(rf.checksum) == 64
            int(rf.checksum, 16)  # must be valid hex

    def test_checksum_is_deterministic_for_same_content(self):
        import hashlib

        with tempfile.TemporaryDirectory() as tmpdir:
            gen = NordicReportGenerator(tmpdir)
            ob = _make_obligation()
            rf = gen.generate(ob)
            h = hashlib.sha256(Path(rf.file_path).read_bytes()).hexdigest()
            assert rf.checksum == h

    def test_filename_contains_country_and_period(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = NordicReportGenerator(tmpdir)
            ob = _make_obligation(country="SE")
            rf = gen.generate(ob)
            fname = Path(rf.file_path).name
            assert "SE" in fname
            assert "2024-01-01" in fname
            assert "2024-12-31" in fname

    def test_report_file_obligation_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = NordicReportGenerator(tmpdir)
            ob = _make_obligation()
            rf = gen.generate(ob)
            assert rf.obligation_id  # non-empty string
            assert "FI" in rf.obligation_id

    def test_empty_obligation_writes_only_total_row(self):
        import csv as csv_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            gen = NordicReportGenerator(tmpdir)
            ob = _make_obligation(weight_by_material={}, fee_amount="0.0000")
            rf = gen.generate(ob)
            with open(rf.file_path) as f:
                rows = list(csv_mod.DictReader(f))
            assert len(rows) == 1
            assert rows[0]["material_type"] == "TOTAL"
            assert rows[0]["fee_amount"] == "0.0000"


# ---------------------------------------------------------------------------
# NordicPROConnector
# ---------------------------------------------------------------------------

class TestNordicPROConnector:
    def test_generate_report_returns_report_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = NordicPROConnector(output_dir=tmpdir)
            ob = _make_obligation()
            rf = conn.generate_report(ob)
            assert isinstance(rf, ReportFile)
            assert Path(rf.file_path).exists()

    def test_submit_report_returns_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = NordicPROConnector(output_dir=tmpdir)
            ob = _make_obligation()
            rf = conn.generate_report(ob)
            result = conn.submit_report(rf, ob)
            assert isinstance(result, SubmissionResult)
            assert result.success is True
            assert result.submission_id is not None
            assert result.error_message is None

    def test_submit_report_reference_starts_with_np(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = NordicPROConnector(output_dir=tmpdir)
            ob = _make_obligation()
            rf = conn.generate_report(ob)
            result = conn.submit_report(rf, ob)
            assert result.submission_id.startswith("NP-")

    def test_submit_report_payload_contains_expected_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = NordicPROConnector(output_dir=tmpdir)
            ob = _make_obligation()
            rf = conn.generate_report(ob)
            result = conn.submit_report(rf, ob)
            payload = result.response_payload
            assert payload["country_code"] == "FI"
            assert payload["status"] == "accepted"
            assert payload["file_checksum"] == rf.checksum

    def test_submit_report_payload_includes_period(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = NordicPROConnector(output_dir=tmpdir)
            ob = _make_obligation()
            rf = conn.generate_report(ob)
            result = conn.submit_report(rf, ob)
            payload = result.response_payload
            assert payload["reporting_period_start"] == "2024-01-01"
            assert payload["reporting_period_end"] == "2024-12-31"

    def test_check_submission_status_returns_acknowledged(self):
        conn = NordicPROConnector()
        status = conn.check_submission_status("NP-ABCDEF123456")
        assert status.acknowledged is True
        assert status.submission_id == "NP-ABCDEF123456"

    def test_two_submissions_have_different_references(self):
        """Each submit call should produce a unique reference."""
        import time
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = NordicPROConnector(output_dir=tmpdir)
            ob = _make_obligation()
            rf = conn.generate_report(ob)
            r1 = conn.submit_report(rf, ob)
            time.sleep(0.01)  # ensure different timestamp
            r2 = conn.submit_report(rf, ob)
            assert r1.submission_id != r2.submission_id

    @pytest.mark.parametrize("country", ["FI", "SE", "NO", "DK"])
    def test_connector_supports_all_nordic_countries(self, country):
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = NordicPROConnector(output_dir=tmpdir)
            ob = _make_obligation(country=country)
            rf = conn.generate_report(ob)
            result = conn.submit_report(rf, ob)
            assert result.success is True
            assert result.response_payload["country_code"] == country
