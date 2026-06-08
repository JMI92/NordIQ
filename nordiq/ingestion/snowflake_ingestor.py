"""Snowflake ingestor — implemented in build step 4."""

from nordiq.ingestion.base import BaseIngestor, DataSourceConfig, NormalizedProductData


class SnowflakeIngestor(BaseIngestor):
    """Ingest product data from a Snowflake table or view. Implemented in build step 4."""

    def fetch(self, config: DataSourceConfig) -> list[NormalizedProductData]:
        raise NotImplementedError("SnowflakeIngestor implemented in build step 4")

    def validate_connection(self, config: DataSourceConfig) -> bool:
        raise NotImplementedError("SnowflakeIngestor implemented in build step 4")
