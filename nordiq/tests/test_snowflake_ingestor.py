"""Unit tests for SnowflakeIngestor — patches snowflake.connector so no real connection needed."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from nordiq.ingestion.base import DataSourceConfig
from nordiq.ingestion.snowflake_ingestor import SnowflakeIngestor
from nordiq.models.enums import DataRecordSource, MaterialType, ProductCategory

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

STANDARD_MAPPING = {
    "external_product_id": "SKU",
    "description": "PRODUCT_NAME",
    "product_category": "CATEGORY",
    "weight_kg": "WEIGHT_KG",
    "material_type": "MATERIAL",
    "reporting_period_start": "PERIOD_START",
    "reporting_period_end": "PERIOD_END",
}

VALID_CONNECTION = {
    "account": "xy12345.eu-west-1",
    "user": "SVC_USER",
    "password": "s3cret",
    "warehouse": "COMPUTE_WH",
    "database": "PROD_DB",
}


def _config(rows=None, mapping=None, table="PRODUCT_WEIGHTS", conn=None):
    return DataSourceConfig(
        source_type="snowflake",
        connection_config=conn or VALID_CONNECTION,
        field_mapping=mapping or STANDARD_MAPPING,
        table_name=table,
    )


# Columns returned by cursor.description match the mapped column names (upper-case).
COLUMNS = ["SKU", "PRODUCT_NAME", "CATEGORY", "WEIGHT_KG", "MATERIAL", "PERIOD_START", "PERIOD_END"]


def _make_row(sku, name, category, weight, material, start, end):
    return (sku, name, category, weight, material, start, end)


def _mock_connector(rows):
    """Return a patch context for snowflake.connector that yields the given rows.

    `import snowflake.connector` resolves as `sys.modules["snowflake"].connector`,
    so we need a two-level mock: a top-level snowflake package mock whose `.connector`
    attribute holds the actual connector mock with `.connect`.
    """
    mock_cursor = MagicMock()
    mock_cursor.description = [(col, None, None, None, None, None, None) for col in COLUMNS]
    mock_cursor.fetchall.return_value = rows

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    mock_connector = MagicMock()
    mock_connector.connect.return_value = mock_conn

    mock_sf = MagicMock()
    mock_sf.connector = mock_connector

    return patch.dict("sys.modules", {"snowflake": mock_sf, "snowflake.connector": mock_connector})


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_fetch_returns_valid_records():
    rows = [
        _make_row("SKU-001", "Plastic Bottle", "packaging", "0.025", "plastic",
                  date(2024, 1, 1), date(2024, 12, 31)),
        _make_row("SKU-002", "Glass Jar", "packaging", "0.200", "glass",
                  date(2024, 1, 1), date(2024, 12, 31)),
    ]
    with _mock_connector(rows):
        records = SnowflakeIngestor().fetch(_config(rows))
    assert len(records) == 2
    assert records[0].external_product_id == "SKU-001"
    assert records[1].external_product_id == "SKU-002"


def test_weight_is_decimal():
    rows = [_make_row("S1", "P", "packaging", "1.500", "plastic", date(2024, 1, 1), date(2024, 12, 31))]
    with _mock_connector(rows):
        records = SnowflakeIngestor().fetch(_config())
    assert isinstance(records[0].weight_kg, Decimal)
    assert records[0].weight_kg == Decimal("1.500")


def test_snowflake_date_objects_accepted():
    """Snowflake driver returns date objects directly — must not fail."""
    rows = [_make_row("S1", "P", "packaging", "0.1", "plastic", date(2024, 1, 1), date(2024, 12, 31))]
    with _mock_connector(rows):
        records = SnowflakeIngestor().fetch(_config())
    assert records[0].reporting_period_start == date(2024, 1, 1)


def test_source_is_snowflake():
    rows = [_make_row("S1", "P", "packaging", "0.1", "plastic", date(2024, 1, 1), date(2024, 12, 31))]
    with _mock_connector(rows):
        records = SnowflakeIngestor().fetch(_config())
    assert records[0].source == DataRecordSource.SNOWFLAKE


def test_raw_record_preserved():
    rows = [_make_row("S1", "MyProd", "packaging", "0.1", "plastic", date(2024, 1, 1), date(2024, 12, 31))]
    with _mock_connector(rows):
        records = SnowflakeIngestor().fetch(_config())
    assert records[0].raw_record["PRODUCT_NAME"] == "MyProd"


# ---------------------------------------------------------------------------
# Error collection
# ---------------------------------------------------------------------------

def test_invalid_weight_collected_not_aborted():
    rows = [
        _make_row("GOOD", "Good", "packaging", "0.5", "plastic", date(2024, 1, 1), date(2024, 12, 31)),
        _make_row("BAD", "Bad", "packaging", "NaN", "plastic", date(2024, 1, 1), date(2024, 12, 31)),
    ]
    with _mock_connector(rows):
        result = SnowflakeIngestor().fetch_with_errors(_config())
    assert result.success_count == 1
    assert result.error_count == 1
    assert result.records[0].external_product_id == "GOOD"


def test_invalid_category_collected():
    rows = [_make_row("X", "P", "INVALID_CAT", "0.1", "plastic", date(2024, 1, 1), date(2024, 12, 31))]
    with _mock_connector(rows):
        result = SnowflakeIngestor().fetch_with_errors(_config())
    assert result.error_count == 1
    assert any("product_category" in e for e in result.row_errors[0].errors)


def test_invalid_material_collected():
    rows = [_make_row("X", "P", "packaging", "0.1", "UNKNOWN_MAT", date(2024, 1, 1), date(2024, 12, 31))]
    with _mock_connector(rows):
        result = SnowflakeIngestor().fetch_with_errors(_config())
    assert result.error_count == 1
    assert any("material_type" in e for e in result.row_errors[0].errors)


def test_negative_weight_collected():
    rows = [_make_row("X", "P", "packaging", "-1.0", "plastic", date(2024, 1, 1), date(2024, 12, 31))]
    with _mock_connector(rows):
        result = SnowflakeIngestor().fetch_with_errors(_config())
    assert result.error_count == 1
    assert any("non-negative" in e for e in result.row_errors[0].errors)


def test_period_end_before_start_collected():
    rows = [_make_row("X", "P", "packaging", "0.1", "plastic", date(2024, 12, 31), date(2024, 1, 1))]
    with _mock_connector(rows):
        result = SnowflakeIngestor().fetch_with_errors(_config())
    assert result.error_count == 1


def test_empty_result_set():
    with _mock_connector([]):
        result = SnowflakeIngestor().fetch_with_errors(_config())
    assert result.success_count == 0
    assert result.error_count == 0


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------

def test_missing_field_mapping_key_raises():
    bad_mapping = {k: v for k, v in STANDARD_MAPPING.items() if k != "weight_kg"}
    with _mock_connector([]):
        with pytest.raises(ValueError, match="weight_kg"):
            SnowflakeIngestor().fetch(_config(mapping=bad_mapping))


def test_missing_connection_key_raises():
    bad_conn = {k: v for k, v in VALID_CONNECTION.items() if k != "password"}
    with _mock_connector([]):
        with pytest.raises(ValueError, match="password"):
            SnowflakeIngestor().fetch(_config(conn=bad_conn))


def test_missing_table_name_raises():
    with _mock_connector([]):
        with pytest.raises(ValueError, match="table_name"):
            SnowflakeIngestor().fetch(_config(table=None))


# ---------------------------------------------------------------------------
# validate_connection
# ---------------------------------------------------------------------------

def test_validate_connection_success():
    with _mock_connector([]):
        assert SnowflakeIngestor().validate_connection(_config()) is True


def test_validate_connection_bad_mapping_returns_false():
    bad_mapping = {k: v for k, v in STANDARD_MAPPING.items() if k != "material_type"}
    assert SnowflakeIngestor().validate_connection(_config(mapping=bad_mapping)) is False


def test_validate_connection_connector_error_returns_false():
    mock_connector = MagicMock()
    mock_connector.connect.side_effect = Exception("network error")
    mock_sf = MagicMock()
    mock_sf.connector = mock_connector
    with patch.dict("sys.modules", {"snowflake": mock_sf, "snowflake.connector": mock_connector}):
        assert SnowflakeIngestor().validate_connection(_config()) is False


# ---------------------------------------------------------------------------
# snowflake.connector not installed
# ---------------------------------------------------------------------------

def test_missing_snowflake_package_raises_import_error():
    # Setting a key to None in sys.modules causes `import <key>` to raise ImportError.
    with patch.dict("sys.modules", {"snowflake": None, "snowflake.connector": None}):
        with pytest.raises((ImportError, TypeError)):
            # Either our ImportError wrapper fires, or Python raises on None module access.
            SnowflakeIngestor().fetch(_config())
