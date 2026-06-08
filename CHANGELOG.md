# Changelog

All notable changes to NordIQ are documented here.

## [Unreleased]

### Added
- Full project scaffold matching the specified directory structure
- Database models: `Customer`, `User`, `CustomerDataSource`, `Product`, `ProductWeight`,
  `EPRObligation`, `EPRRate`, `ReportingDeadline`, `PROSubmission`, `AuditLog`, `ImportJob`
- Alembic migration `0001_initial_schema` — creates all tables with indexes and foreign keys
- Alembic migration `0002_seed_nordic_epr_rates` — seeds indicative 2024 EPR rates for
  FI/SE/NO/DK packaging and reporting deadlines
- Enum definitions for all domain types (`ProductCategory`, `MaterialType`, etc.)
- ORM mixins: `UUIDPrimaryKeyMixin`, `TimestampMixin`, `CustomerScopedMixin`
- Core app configuration via `pydantic-settings` (`.env` support)
- Database session factory with async SQLAlchemy
- Security helpers: bcrypt password hashing, JWT generation/validation, Fernet credential encryption
- FastAPI app skeleton with health check endpoint (`GET /health`)
- Stub routers for all planned API endpoints
- Abstract base classes: `BaseIngestor`, `EPRCalculator`, `BasePROConnector`
- `NormalizedProductData` dataclass — canonical internal product record schema
- Skeleton implementations: `CSVIngestor`, `SnowflakeIngestor`, `NordicPackagingCalculator`,
  `NordicPROConnector`, `NordicReportGenerator`
- Calculator registry pattern
- Streamlit frontend entry point (stub)
- APScheduler job stubs
- Unit tests for models, enums, security helpers, and normalizer validation
- `Dockerfile` and `docker-compose.yml`
- `.env.example` with all required environment variables documented
