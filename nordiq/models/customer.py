"""Customer (tenant) and their data source configuration models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nordiq.core.database import Base
from nordiq.models.enums import DataSourceType
from nordiq.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A paying customer — the top-level tenant entity.

    All other records belong to exactly one Customer. Queries MUST always
    filter by customer_id to prevent cross-tenant data leakage.
    """

    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    vat_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    country_of_incorporation: Mapped[str] = mapped_column(String(2), nullable=False)  # ISO 3166-1 alpha-2
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="customer", cascade="all, delete-orphan")  # type: ignore[name-defined]
    data_sources: Mapped[list["CustomerDataSource"]] = relationship(
        "CustomerDataSource", back_populates="customer", cascade="all, delete-orphan"
    )
    products: Mapped[list["Product"]] = relationship("Product", back_populates="customer", cascade="all, delete-orphan")  # type: ignore[name-defined]
    obligations: Mapped[list["EPRObligation"]] = relationship("EPRObligation", back_populates="customer", cascade="all, delete-orphan")  # type: ignore[name-defined]
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="customer", cascade="all, delete-orphan")  # type: ignore[name-defined]
    import_jobs: Mapped[list["ImportJob"]] = relationship("ImportJob", back_populates="customer", cascade="all, delete-orphan")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<Customer {self.name} ({self.id})>"


class CustomerDataSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Configuration for a customer's data source (Snowflake, CSV, API).

    connection_config stores encrypted JSON — never store plaintext credentials.
    field_mapping maps source column names to NordIQ's NormalizedProductData schema.
    """

    __tablename__ = "customer_data_sources"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[DataSourceType] = mapped_column(String(50), nullable=False)
    # Encrypted JSON blob — decrypted only when establishing a connection
    connection_config: Mapped[str | None] = mapped_column(Text, nullable=True)
    # For Snowflake: the fully-qualified table/view name
    table_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # JSON: maps source field names → NormalizedProductData field names
    field_mapping: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="data_sources")
    import_jobs: Mapped[list["ImportJob"]] = relationship("ImportJob", back_populates="data_source")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<CustomerDataSource {self.name} ({self.source_type})>"
