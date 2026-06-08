"""CSV ingestor — reads product weight records from a CSV file or file-like object.

Field mapping config (field_mapping in DataSourceConfig) maps canonical field names
to the actual CSV column headers in the customer's file:

    {
        "external_product_id": "SKU",
        "description": "Product Name",
        "product_category": "Category",
        "weight_kg": "Weight (kg)",
        "material_type": "Material",
        "reporting_period_start": "Period Start",  # YYYY-MM-DD
        "reporting_period_end": "Period End"        # YYYY-MM-DD
    }

All mapped fields are required. Rows with missing/invalid values are collected as
RowError entries and skipped — ingestion continues for remaining rows.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import IO

from nordiq.ingestion.base import BaseIngestor, DataSourceConfig, NormalizedProductData
from nordiq.ingestion.normalizer import validate_normalized_record
from nordiq.models.enums import DataRecordSource, MaterialType, ProductCategory

REQUIRED_MAPPED_FIELDS = (
    "external_product_id",
    "description",
    "product_category",
    "weight_kg",
    "material_type",
    "reporting_period_start",
    "reporting_period_end",
)

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%m/%d/%Y")


@dataclass
class RowError:
    row_number: int  # 1-based, excluding header
    raw_row: dict
    errors: list[str]


@dataclass
class CSVIngestionResult:
    records: list[NormalizedProductData]
    row_errors: list[RowError]

    @property
    def error_count(self) -> int:
        return len(self.row_errors)

    @property
    def success_count(self) -> int:
        return len(self.records)


def _parse_date(value: str, field: str) -> date:
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"{field}: cannot parse date '{value}' — expected YYYY-MM-DD or DD/MM/YYYY")


def _parse_weight(value: str) -> Decimal:
    try:
        return Decimal(value.strip())
    except InvalidOperation:
        raise ValueError(f"weight_kg: cannot parse '{value}' as a decimal number")


def _parse_enum(value: str, enum_cls, field: str):
    normalised = value.strip().lower()
    try:
        return enum_cls(normalised)
    except ValueError:
        valid = [e.value for e in enum_cls]
        raise ValueError(f"{field}: '{value}' is not a valid value; expected one of {valid}")


def _validate_field_mapping(field_mapping: dict) -> list[str]:
    missing = [f for f in REQUIRED_MAPPED_FIELDS if f not in field_mapping]
    return [f"field_mapping is missing required key '{f}'" for f in missing]


def _get_cell(row: dict, canonical: str, field_mapping: dict) -> str:
    csv_col = field_mapping[canonical]
    value = row.get(csv_col)
    if value is None:
        raise ValueError(f"column '{csv_col}' not found in CSV header")
    return value


class CSVIngestor(BaseIngestor):
    """Ingest product weight records from a CSV file."""

    def fetch(self, config: DataSourceConfig) -> list[NormalizedProductData]:
        """Fetch valid records only; errors are silently dropped.

        Use fetch_with_errors() to inspect per-row failures.
        """
        return self.fetch_with_errors(config).records

    def fetch_with_errors(self, config: DataSourceConfig) -> CSVIngestionResult:
        """Fetch all rows and return both valid records and per-row errors."""
        mapping_errors = _validate_field_mapping(config.field_mapping)
        if mapping_errors:
            raise ValueError("; ".join(mapping_errors))

        conn = config.connection_config
        file_path = conn.get("file_path")
        inline_content = conn.get("content")

        if file_path is not None:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"CSV file not found: {path}")
            file_obj: IO = path.open(newline="", encoding="utf-8")
            close_after = True
        elif inline_content is not None:
            file_obj = io.StringIO(inline_content)
            close_after = True
        else:
            raise ValueError("connection_config must contain 'file_path' or 'content'")

        try:
            return self._parse(file_obj, config.field_mapping)
        finally:
            if close_after:
                file_obj.close()

    def _parse(self, file_obj: IO, field_mapping: dict) -> CSVIngestionResult:
        reader = csv.DictReader(file_obj)
        records: list[NormalizedProductData] = []
        row_errors: list[RowError] = []

        for row_idx, raw_row in enumerate(reader, start=1):
            errors: list[str] = []

            try:
                ext_id = _get_cell(raw_row, "external_product_id", field_mapping).strip()
                description = _get_cell(raw_row, "description", field_mapping).strip()
                weight_raw = _get_cell(raw_row, "weight_kg", field_mapping)
                category_raw = _get_cell(raw_row, "product_category", field_mapping)
                material_raw = _get_cell(raw_row, "material_type", field_mapping)
                start_raw = _get_cell(raw_row, "reporting_period_start", field_mapping)
                end_raw = _get_cell(raw_row, "reporting_period_end", field_mapping)
            except ValueError as exc:
                row_errors.append(RowError(row_idx, dict(raw_row), [str(exc)]))
                continue

            weight_kg = None
            try:
                weight_kg = _parse_weight(weight_raw)
            except ValueError as exc:
                errors.append(str(exc))

            product_category = None
            try:
                product_category = _parse_enum(category_raw, ProductCategory, "product_category")
            except ValueError as exc:
                errors.append(str(exc))

            material_type = None
            try:
                material_type = _parse_enum(material_raw, MaterialType, "material_type")
            except ValueError as exc:
                errors.append(str(exc))

            period_start = None
            try:
                period_start = _parse_date(start_raw, "reporting_period_start")
            except ValueError as exc:
                errors.append(str(exc))

            period_end = None
            try:
                period_end = _parse_date(end_raw, "reporting_period_end")
            except ValueError as exc:
                errors.append(str(exc))

            if period_start and period_end and period_end < period_start:
                errors.append("reporting_period_end must not be before reporting_period_start")

            if errors:
                row_errors.append(RowError(row_idx, dict(raw_row), errors))
                continue

            record = NormalizedProductData(
                external_product_id=ext_id,
                description=description,
                product_category=product_category,
                weight_kg=weight_kg,
                material_type=material_type,
                reporting_period_start=period_start,
                reporting_period_end=period_end,
                source=DataRecordSource.CSV,
                raw_record=dict(raw_row),
            )

            domain_errors = validate_normalized_record(record)
            if domain_errors:
                row_errors.append(RowError(row_idx, dict(raw_row), domain_errors))
            else:
                records.append(record)

        return CSVIngestionResult(records=records, row_errors=row_errors)

    def validate_connection(self, config: DataSourceConfig) -> bool:
        """Return True if the file exists and the field mapping covers all required fields."""
        if _validate_field_mapping(config.field_mapping):
            return False
        file_path = config.connection_config.get("file_path")
        return file_path is not None and Path(file_path).exists()
