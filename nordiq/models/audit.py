"""Audit log and import job tracking models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nordiq.core.database import Base
from nordiq.models.enums import DataSourceType, ImportJobStatus
from nordiq.models.mixins import UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin, Base):
    """Immutable record of every significant action in the system.

    Legal requirement for compliance software: every data import, calculation,
    and submission must be traceable to a user and a point in time.
    AuditLog rows are NEVER updated or deleted.
    """

    __tablename__ = "audit_log"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="audit_logs")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} on {self.entity_type}:{self.entity_id}>"


class ImportJob(UUIDPrimaryKeyMixin, Base):
    """Tracks the lifecycle of a data import operation.

    Created when a sync or upload starts; updated as records are processed.
    On completion stores a summary; on failure stores error details for display
    in the Data Sources UI.
    """

    __tablename__ = "import_jobs"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    data_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_data_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_type: Mapped[DataSourceType] = mapped_column(String(50), nullable=False)
    status: Mapped[ImportJobStatus] = mapped_column(
        String(20), nullable=False, default=ImportJobStatus.PENDING, index=True
    )
    records_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="import_jobs")  # type: ignore[name-defined]
    data_source: Mapped["CustomerDataSource"] = relationship("CustomerDataSource", back_populates="import_jobs")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<ImportJob {self.source_type} [{self.status}] {self.records_processed} records>"
