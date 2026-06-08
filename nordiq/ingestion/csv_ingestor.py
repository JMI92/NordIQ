"""CSV/Excel ingestor — implemented in build step 3."""

from nordiq.ingestion.base import BaseIngestor, DataSourceConfig, NormalizedProductData


class CSVIngestor(BaseIngestor):
    """Ingest product data from CSV or Excel files. Implemented in build step 3."""

    def fetch(self, config: DataSourceConfig) -> list[NormalizedProductData]:
        raise NotImplementedError("CSVIngestor implemented in build step 3")

    def validate_connection(self, config: DataSourceConfig) -> bool:
        raise NotImplementedError("CSVIngestor implemented in build step 3")
