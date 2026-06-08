"""Unit tests for CSVIngestor — field mapping, parsing, validation, error collection."""

from decimal import Decimal
from textwrap import dedent

import pytest

from nordiq.ingestion.base import DataSourceConfig
from nordiq.ingestion.csv_ingestor import CSVIngestor, _parse_date, _parse_weight
from nordiq.models.enums import DataRecordSource, MaterialType, ProductCategory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STANDARD_MAPPING = {
    "external_product_id": "SKU",
    "description": "Name",
    "product_category": "Category",
    "weight_kg": "Weight",
    "material_type": "Material",
    "reporting_period_start": "Start",
    "reporting_period_end": "End",
}


def _config(content: str, mapping: dict | None = None) -> DataSourceConfig:
    return DataSourceConfig(
        source_type="csv",
        connection_config={"content": content},
        field_mapping=mapping or STANDARD_MAPPING,
    )


VALID_CSV = dedent("""\
    SKU,Name,Category,Weight,Material,Start,End
    SKU-001,Plastic Bottle,packaging,0.025,plastic,2024-01-01,2024-12-31
    SKU-002,Glass Jar,packaging,0.200,glass,2024-01-01,2024-12-31
""")

# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_fetch_returns_valid_records():
    ingestor = CSVIngestor()
    records = ingestor.fetch(_config(VALID_CSV))
    assert len(records) == 2
    assert records[0].external_product_id == "SKU-001"
    assert records[1].external_product_id == "SKU-002"


def test_weight_parsed_as_decimal():
    ingestor = CSVIngestor()
    records = ingestor.fetch(_config(VALID_CSV))
    assert isinstance(records[0].weight_kg, Decimal)
    assert records[0].weight_kg == Decimal("0.025")


def test_enums_parsed_correctly():
    ingestor = CSVIngestor()
    records = ingestor.fetch(_config(VALID_CSV))
    assert records[0].product_category == ProductCategory.PACKAGING
    assert records[0].material_type == MaterialType.PLASTIC
    assert records[1].material_type == MaterialType.GLASS


def test_source_is_csv():
    ingestor = CSVIngestor()
    records = ingestor.fetch(_config(VALID_CSV))
    assert all(r.source == DataRecordSource.CSV for r in records)


def test_raw_record_preserved():
    ingestor = CSVIngestor()
    records = ingestor.fetch(_config(VALID_CSV))
    assert records[0].raw_record["SKU"] == "SKU-001"


# ---------------------------------------------------------------------------
# Date format variations
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("date_str,expected", [
    ("2024-01-15", (2024, 1, 15)),
    ("15/01/2024", (2024, 1, 15)),
    ("15.01.2024", (2024, 1, 15)),
    ("01/15/2024", (2024, 1, 15)),
])
def test_date_format_variations(date_str, expected):
    from datetime import date
    result = _parse_date(date_str, "test_field")
    assert result == date(*expected)


# ---------------------------------------------------------------------------
# Error collection — bad rows don't abort ingestion
# ---------------------------------------------------------------------------

def test_invalid_weight_collected_as_error():
    csv_content = dedent("""\
        SKU,Name,Category,Weight,Material,Start,End
        GOOD,Valid product,packaging,0.1,plastic,2024-01-01,2024-12-31
        BAD,Bad weight,packaging,not-a-number,plastic,2024-01-01,2024-12-31
    """)
    ingestor = CSVIngestor()
    result = ingestor.fetch_with_errors(_config(csv_content))
    assert result.success_count == 1
    assert result.error_count == 1
    assert result.records[0].external_product_id == "GOOD"
    assert any("weight_kg" in e for e in result.row_errors[0].errors)


def test_invalid_enum_collected_as_error():
    csv_content = dedent("""\
        SKU,Name,Category,Weight,Material,Start,End
        BAD,Product,NOT_A_CATEGORY,0.1,plastic,2024-01-01,2024-12-31
    """)
    ingestor = CSVIngestor()
    result = ingestor.fetch_with_errors(_config(csv_content))
    assert result.success_count == 0
    assert result.error_count == 1
    assert any("product_category" in e for e in result.row_errors[0].errors)


def test_negative_weight_collected_as_error():
    csv_content = dedent("""\
        SKU,Name,Category,Weight,Material,Start,End
        NEG,Negative,packaging,-0.5,plastic,2024-01-01,2024-12-31
    """)
    ingestor = CSVIngestor()
    result = ingestor.fetch_with_errors(_config(csv_content))
    assert result.success_count == 0
    assert result.error_count == 1
    assert any("non-negative" in e for e in result.row_errors[0].errors)


def test_period_end_before_start_collected_as_error():
    csv_content = dedent("""\
        SKU,Name,Category,Weight,Material,Start,End
        INV,Inverted period,packaging,0.1,plastic,2024-12-31,2024-01-01
    """)
    ingestor = CSVIngestor()
    result = ingestor.fetch_with_errors(_config(csv_content))
    assert result.error_count == 1
    assert any("reporting_period_end" in e for e in result.row_errors[0].errors)


def test_multiple_errors_on_same_row():
    csv_content = dedent("""\
        SKU,Name,Category,Weight,Material,Start,End
        X,Multi-error,BAD_CAT,bad_weight,BAD_MAT,2024-01-01,2024-12-31
    """)
    ingestor = CSVIngestor()
    result = ingestor.fetch_with_errors(_config(csv_content))
    assert result.error_count == 1
    # Three parse errors: category, weight, material
    assert len(result.row_errors[0].errors) >= 3


def test_good_rows_after_bad_row_are_included():
    csv_content = dedent("""\
        SKU,Name,Category,Weight,Material,Start,End
        BAD,Bad,packaging,not-a-number,plastic,2024-01-01,2024-12-31
        GOOD,Good,packaging,0.5,plastic,2024-01-01,2024-12-31
    """)
    ingestor = CSVIngestor()
    result = ingestor.fetch_with_errors(_config(csv_content))
    assert result.success_count == 1
    assert result.records[0].external_product_id == "GOOD"


# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------

def test_custom_field_mapping():
    csv_content = dedent("""\
        product_sku,product_name,cat,wt,mat,from,to
        P-001,Cardboard Box,packaging,0.3,paper,2024-01-01,2024-12-31
    """)
    mapping = {
        "external_product_id": "product_sku",
        "description": "product_name",
        "product_category": "cat",
        "weight_kg": "wt",
        "material_type": "mat",
        "reporting_period_start": "from",
        "reporting_period_end": "to",
    }
    ingestor = CSVIngestor()
    records = ingestor.fetch(_config(csv_content, mapping))
    assert len(records) == 1
    assert records[0].external_product_id == "P-001"
    assert records[0].material_type == MaterialType.PAPER


def test_missing_field_mapping_key_raises():
    incomplete_mapping = {k: v for k, v in STANDARD_MAPPING.items() if k != "weight_kg"}
    ingestor = CSVIngestor()
    with pytest.raises(ValueError, match="weight_kg"):
        ingestor.fetch(_config(VALID_CSV, incomplete_mapping))


def test_missing_csv_column_collected_as_error():
    # CSV doesn't have the column the mapping points to
    csv_content = dedent("""\
        SKU,Name,Category,WRONG_COL,Material,Start,End
        P-001,Product,packaging,0.1,plastic,2024-01-01,2024-12-31
    """)
    ingestor = CSVIngestor()
    result = ingestor.fetch_with_errors(_config(csv_content))
    assert result.error_count == 1


# ---------------------------------------------------------------------------
# validate_connection
# ---------------------------------------------------------------------------

def test_validate_connection_missing_file(tmp_path):
    config = DataSourceConfig(
        source_type="csv",
        connection_config={"file_path": str(tmp_path / "nonexistent.csv")},
        field_mapping=STANDARD_MAPPING,
    )
    assert CSVIngestor().validate_connection(config) is False


def test_validate_connection_existing_file(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text(VALID_CSV)
    config = DataSourceConfig(
        source_type="csv",
        connection_config={"file_path": str(f)},
        field_mapping=STANDARD_MAPPING,
    )
    assert CSVIngestor().validate_connection(config) is True


def test_validate_connection_bad_mapping(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text(VALID_CSV)
    bad_mapping = {k: v for k, v in STANDARD_MAPPING.items() if k != "material_type"}
    config = DataSourceConfig(
        source_type="csv",
        connection_config={"file_path": str(f)},
        field_mapping=bad_mapping,
    )
    assert CSVIngestor().validate_connection(config) is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_csv_returns_empty_result():
    csv_content = "SKU,Name,Category,Weight,Material,Start,End\n"
    ingestor = CSVIngestor()
    result = ingestor.fetch_with_errors(_config(csv_content))
    assert result.success_count == 0
    assert result.error_count == 0


def test_no_file_path_or_content_raises():
    config = DataSourceConfig(
        source_type="csv",
        connection_config={},
        field_mapping=STANDARD_MAPPING,
    )
    with pytest.raises(ValueError, match="file_path"):
        CSVIngestor().fetch(config)


def test_row_number_is_correct():
    csv_content = dedent("""\
        SKU,Name,Category,Weight,Material,Start,End
        GOOD1,Good,packaging,0.1,plastic,2024-01-01,2024-12-31
        BAD,Bad,packaging,oops,plastic,2024-01-01,2024-12-31
        GOOD2,Good,packaging,0.2,plastic,2024-01-01,2024-12-31
    """)
    ingestor = CSVIngestor()
    result = ingestor.fetch_with_errors(_config(csv_content))
    assert result.row_errors[0].row_number == 2
