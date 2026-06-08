"""Smoke tests for ORM models — verifies all models import and have expected attributes."""

import uuid
from datetime import date, datetime, timezone

import pytest

from nordiq.models.enums import (
    DataRecordSource,
    DataSourceType,
    ImportJobStatus,
    MaterialType,
    ObligationStatus,
    ProductCategory,
    SubmissionMethod,
    SubmissionStatus,
)


def test_product_category_values():
    assert ProductCategory.PACKAGING == "packaging"
    assert ProductCategory.WEEE == "weee"
    assert ProductCategory.BATTERIES == "batteries"


def test_material_type_values():
    assert MaterialType.PLASTIC == "plastic"
    assert MaterialType.PAPER == "paper"
    assert MaterialType.GLASS == "glass"
    assert MaterialType.METAL == "metal"


def test_obligation_status_values():
    assert ObligationStatus.DRAFT == "draft"
    assert ObligationStatus.FINALISED == "finalised"
    assert ObligationStatus.SUBMITTED == "submitted"


def test_submission_status_values():
    assert SubmissionStatus.PENDING == "pending"
    assert SubmissionStatus.SUCCESS == "success"
    assert SubmissionStatus.FAILED == "failed"
    assert SubmissionStatus.ACKNOWLEDGED == "acknowledged"


def test_import_job_status_values():
    assert ImportJobStatus.PENDING == "pending"
    assert ImportJobStatus.RUNNING == "running"
    assert ImportJobStatus.COMPLETED == "completed"
    assert ImportJobStatus.FAILED == "failed"


def test_normalized_product_data_import():
    from nordiq.ingestion.base import NormalizedProductData
    record = NormalizedProductData(
        external_product_id="SKU-001",
        description="Plastic bottle 0.5L",
        product_category=ProductCategory.PACKAGING,
        weight_kg=0.025,
        material_type=MaterialType.PLASTIC,
        reporting_period_start=date(2024, 1, 1),
        reporting_period_end=date(2024, 12, 31),
        source=DataRecordSource.CSV,
        raw_record={"sku": "SKU-001", "weight": "0.025"},
    )
    assert record.external_product_id == "SKU-001"
    assert record.product_category == ProductCategory.PACKAGING
    assert record.material_type == MaterialType.PLASTIC


def test_normalizer_catches_negative_weight():
    from nordiq.ingestion.base import NormalizedProductData
    from nordiq.ingestion.normalizer import validate_normalized_record
    record = NormalizedProductData(
        external_product_id="BAD-001",
        description="Bad record",
        product_category=ProductCategory.PACKAGING,
        weight_kg=-1.0,
        material_type=MaterialType.PLASTIC,
        reporting_period_start=date(2024, 1, 1),
        reporting_period_end=date(2024, 12, 31),
        source=DataRecordSource.CSV,
        raw_record={},
    )
    errors = validate_normalized_record(record)
    assert any("non-negative" in e for e in errors)


def test_normalizer_warns_on_zero_weight():
    from nordiq.ingestion.base import NormalizedProductData
    from nordiq.ingestion.normalizer import validate_normalized_record
    record = NormalizedProductData(
        external_product_id="ZERO-001",
        description="Zero weight",
        product_category=ProductCategory.PACKAGING,
        weight_kg=0,
        material_type=MaterialType.PAPER,
        reporting_period_start=date(2024, 1, 1),
        reporting_period_end=date(2024, 12, 31),
        source=DataRecordSource.MANUAL,
        raw_record={},
    )
    errors = validate_normalized_record(record)
    assert any("0" in e for e in errors)
