"""Snowflake ingestor — fetches product weight records from a Snowflake table or view.

connection_config (decrypted from CustomerDataSource.connection_config) must contain:

    {
        "account":   "xy12345.eu-west-1",
        "user":      "NORDIQ_SVC",
        "password":  "...",
        "warehouse": "COMPUTE_WH",
        "database":  "PROD_DB",
        "schema":    "PUBLIC"        # optional, default "PUBLIC"
    }

field_mapping maps canonical field names to actual column names in the Snowflake table,
identical in structure to CSVIngestor (see csv_ingestor.py).

The ingestor issues a single parameterised SELECT using the mapped column names and the
configured table_name. No DDL, no writes — read-only by design.

Error handling mirrors CSVIngestor: per-row errors are collected rather than aborting
the whole fetch. Use fetch_with_errors() for the full result including errors.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

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

REQUIRED_CONNECTION_KEYS = ("account", "user", "password", "warehouse", "database")


@dataclass
class RowError:
    row_number: int
    raw_row: dict
    errors: list[str]


@dataclass
class SnowflakeIngestionResult:
    records: list[NormalizedProductData]
    row_errors: list[RowError]

    @property
    def error_count(self) -> int:
        return len(self.row_errors)

    @property
    def success_count(self) -> int:
        return len(self.records)


def _validate_field_mapping(field_mapping: dict) -> list[str]:
    missing = [f for f in REQUIRED_MAPPED_FIELDS if f not in field_mapping]
    return [f"field_mapping is missing required key '{f}'" for f in missing]


def _validate_connection_config(conn: dict) -> list[str]:
    missing = [k for k in REQUIRED_CONNECTION_KEYS if not conn.get(k)]
    return [f"connection_config is missing required key '{k}'" for k in missing]


def _parse_weight(value) -> Decimal:
    try:
        d = Decimal(str(value).strip())
    except InvalidOperation:
        raise ValueError(f"weight_kg: cannot parse '{value}' as a decimal number")
    if not d.is_finite():
        raise ValueError(f"weight_kg: '{value}' is not a finite number")
    return d


def _parse_enum(value, enum_cls, field: str):
    normalised = str(value).strip().lower()
    try:
        return enum_cls(normalised)
    except ValueError:
        valid = [e.value for e in enum_cls]
        raise ValueError(f"{field}: '{value}' is not a valid value; expected one of {valid}")


def _to_date(value, field: str) -> date:
    if isinstance(value, date):
        return value
    # Snowflake may return datetime — extract date part
    if hasattr(value, "date"):
        return value.date()
    from datetime import datetime
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"{field}: cannot parse '{value}' as a date")


def _build_select(table_name: str, field_mapping: dict) -> str:
    cols = ", ".join(f'"{field_mapping[f]}"' for f in REQUIRED_MAPPED_FIELDS)
    return f"SELECT {cols} FROM {table_name}"  # noqa: S608 — table_name is from trusted config


class SnowflakeIngestor(BaseIngestor):
    """Ingest product weight records from a Snowflake table or view."""

    def fetch(self, config: DataSourceConfig) -> list[NormalizedProductData]:
        """Fetch valid records only. Use fetch_with_errors() for error details."""
        return self.fetch_with_errors(config).records

    def fetch_with_errors(self, config: DataSourceConfig) -> SnowflakeIngestionResult:
        """Execute SELECT and return both valid records and per-row errors."""
        self._assert_valid_config(config)
        conn = self._connect(config.connection_config)
        try:
            cursor = conn.cursor()
            sql = _build_select(config.table_name, config.field_mapping)
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
        finally:
            conn.close()

        return self._parse_rows(rows, columns, config.field_mapping)

    def validate_connection(self, config: DataSourceConfig) -> bool:
        """Return True if Snowflake is reachable and the table is accessible."""
        errors = _validate_field_mapping(config.field_mapping) + _validate_connection_config(
            config.connection_config
        )
        if errors:
            return False
        try:
            conn = self._connect(config.connection_config)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                # Also verify the target table exists and is readable.
                if config.table_name:
                    cols = ", ".join(
                        f'"{config.field_mapping[f]}"' for f in REQUIRED_MAPPED_FIELDS
                    )
                    cursor.execute(f"SELECT {cols} FROM {config.table_name} LIMIT 0")  # noqa: S608
            finally:
                conn.close()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _assert_valid_config(self, config: DataSourceConfig) -> None:
        errors = _validate_field_mapping(config.field_mapping) + _validate_connection_config(
            config.connection_config
        )
        if errors:
            raise ValueError("; ".join(errors))
        if not config.table_name:
            raise ValueError("DataSourceConfig.table_name is required for SnowflakeIngestor")

    @staticmethod
    def _connect(conn_cfg: dict):
        try:
            import snowflake.connector  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "snowflake-connector-python is required for SnowflakeIngestor. "
                "Install it with: pip install snowflake-connector-python"
            ) from exc

        return snowflake.connector.connect(
            account=conn_cfg["account"],
            user=conn_cfg["user"],
            password=conn_cfg["password"],
            warehouse=conn_cfg["warehouse"],
            database=conn_cfg["database"],
            schema=conn_cfg.get("schema", "PUBLIC"),
            # Short timeouts — fail fast rather than hanging
            login_timeout=15,
            network_timeout=30,
        )

    def _parse_rows(
        self, rows: list, columns: list[str], field_mapping: dict
    ) -> SnowflakeIngestionResult:
        # Map canonical field → column index; case-insensitive to handle driver variations
        col_index = {col.upper(): idx for idx, col in enumerate(columns)}
        try:
            canonical_idx = {
                f: col_index[field_mapping[f].upper()] for f in REQUIRED_MAPPED_FIELDS
            }
        except KeyError as exc:
            raise ValueError(
                f"Column {exc} not found in query result. "
                f"Available columns: {columns}"
            ) from exc

        records: list[NormalizedProductData] = []
        row_errors: list[RowError] = []

        for row_number, row in enumerate(rows, start=1):
            raw_row = dict(zip(columns, row))
            errors: list[str] = []

            ext_id = str(row[canonical_idx["external_product_id"]]).strip()
            description = str(row[canonical_idx["description"]]).strip()

            weight_kg = None
            try:
                weight_kg = _parse_weight(row[canonical_idx["weight_kg"]])
            except ValueError as exc:
                errors.append(str(exc))

            product_category = None
            try:
                product_category = _parse_enum(
                    row[canonical_idx["product_category"]], ProductCategory, "product_category"
                )
            except ValueError as exc:
                errors.append(str(exc))

            material_type = None
            try:
                material_type = _parse_enum(
                    row[canonical_idx["material_type"]], MaterialType, "material_type"
                )
            except ValueError as exc:
                errors.append(str(exc))

            period_start = None
            try:
                period_start = _to_date(
                    row[canonical_idx["reporting_period_start"]], "reporting_period_start"
                )
            except ValueError as exc:
                errors.append(str(exc))

            period_end = None
            try:
                period_end = _to_date(
                    row[canonical_idx["reporting_period_end"]], "reporting_period_end"
                )
            except ValueError as exc:
                errors.append(str(exc))

            if period_start and period_end and period_end < period_start:
                errors.append("reporting_period_end must not be before reporting_period_start")

            if errors:
                row_errors.append(RowError(row_number, raw_row, errors))
                continue

            record = NormalizedProductData(
                external_product_id=ext_id,
                description=description,
                product_category=product_category,
                weight_kg=weight_kg,
                material_type=material_type,
                reporting_period_start=period_start,
                reporting_period_end=period_end,
                source=DataRecordSource.SNOWFLAKE,
                raw_record=raw_row,
            )

            domain_errors = validate_normalized_record(record)
            if domain_errors:
                row_errors.append(RowError(row_number, raw_row, domain_errors))
            else:
                records.append(record)

        return SnowflakeIngestionResult(records=records, row_errors=row_errors)
