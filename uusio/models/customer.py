"""Customer (tenant) and their data source configuration models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from uusio.core.database import Base
from uusio.models.enums import DataSourceType
from uusio.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    vat_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    country_of_incorporation: Mapped[str] = mapped_column(String(2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    users: Mapped[list["User"]] = relationship("User", back_populates="customer", cascade="all, delete-orphan")  # type: ignore[name-defined]
    data_sources: Mapped[list["CustomerDataSource"]] = relationship("CustomerDataSource", back_populates="customer", cascade="all, delete-orphan")
    products: Mapped[list["Product"]] = relationship("Product", back_populates="customer", cascade="all, delete-orphan")  # type: ignore[name-defined]
    obligations: Mapped[list["EPRObligation"]] = relationship("EPRObligation", back_populates="customer", cascade="all, delete-orphan")  # type: ignore[name-defined]
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="customer", cascade="all, delete-orphan")  # type: ignore[name-defined]
    import_jobs: Mapped[list["ImportJob"]] = relationship("ImportJob", back_populates="customer", cascade="all, delete-orphan")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<Customer {self.name} ({self.id})>"


class CustomerDataSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_data_sources"

    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[DataSourceType] = mapped_column(String(50), nullable=False)
    connection_config: Mapped[str | None] = mapped_column(Text, nullable=True)
    table_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    field_mapping: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="data_sources")
    import_jobs: Mapped[list["ImportJob"]] = relationship("ImportJob", back_populates="data_source")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<CustomerDataSource {self.name} ({self.source_type})>"
