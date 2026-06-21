"""Abstract base class for all data ingestors — implemented in build step 3/4."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

from uusio.models.enums import DataRecordSource, MaterialType, ProductCategory


@dataclass
class DataSourceConfig:
    source_type: str
    connection_config: dict  # decrypted
    field_mapping: dict
    table_name: str | None = None
    last_synced_at: date | None = None


@dataclass
class NormalizedProductData:
    """Canonical internal representation of a product weight record.

    All ingestors MUST produce this type. The calculation engine ONLY
    accepts NormalizedProductData — it never reads raw source records.
    """
    external_product_id: str
    description: str
    product_category: ProductCategory
    weight_kg: float  # stored as Decimal in DB — ingestor must validate non-negative
    material_type: MaterialType
    reporting_period_start: date
    reporting_period_end: date
    source: DataRecordSource
    raw_record: dict  # original record for audit trail


class BaseIngestor(ABC):
    """Base class for all data source ingestors."""

    @abstractmethod
    def fetch(self, config: DataSourceConfig) -> list[NormalizedProductData]:
        """Fetch and normalise records from the data source."""
        ...

    @abstractmethod
    def validate_connection(self, config: DataSourceConfig) -> bool:
        """Test that the connection is reachable and the schema looks correct."""
        ...
